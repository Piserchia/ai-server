# Xiaomi MiMo-V2.6-Pro — research (as of 2026-09-24)

Research method note: this session's web-search budget was exhausted before this task started, so
everything below comes from direct fetches of primary pages (Xiaomi platform docs via their sitemap,
Hugging Face model cards, OpenRouter's JSON API, Artificial Analysis, GitHub) plus HN threads and press
found through Google News RSS and HN's Algolia API. Reddit and X could not be fetched from this
environment; community sentiment therefore leans on Hacker News. Every number cites a source by
[n]; anything I could not confirm is marked "(unverified)".

## 1. Snapshot

**Company.** Xiaomi's MiMo team (mimo.xiaomi.com; contact mimo@xiaomi.com), led publicly by Luo Fuli
[43]. The lab positions itself as "frontier intelligence, all the modalities, built in public" [39] and
released the V2.6 family on 2026-09-21/22 (official release note dated 2026-09-22 Beijing; OpenRouter listing
and HN thread 2026-09-21 20:07/20:12 UTC; forkast's 09-17 article [43] covers the public RL run that preceded
release, not the release itself — exact date unverified as of 2026-09-24) with weights, ~7,000 RL environments and the training
framework under MIT [13][24][27].

**Current lineup (API IDs on Xiaomi's platform; lowercase required) [13][19]:**

| API model ID | HF weights | Params (total/active) | Context / max output | Input modalities | Output |
|---|---|---|---|---|---|
| `mimo-v2.6-pro` | `XiaomiMiMo/MiMo-V2.6-Pro-RL` | 1.02T / 42B MoE (384 experts, 8 active, 70 layers) [24] | 1M / 128K [1] | text, image, video, audio [1] | text |
| `mimo-v2.6-flash` | `XiaomiMiMo/MiMo-V2.6-Flash-RL` | 309B / 15B MoE [25] | 1M / 128K [2] | text, image, video, audio [2] | text |
| `mimo-v2.6-pro-ultraspeed` | (same Pro weights, FP4 + speculative-decoding serving) | as Pro | 1M / 128K [19] | same | text |
| `mimo-v2.6-distill-qwen-9b` | `XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B` (base Qwen3.5-9B) | 9B dense [26] | not stated | text + image [26] | text |
| `mimo-v2.5-pro`, `mimo-v2.5` | open (MIT) | — | 1M / 128K | — | text; **deprecated 2026-10-21 10:00 Beijing** [14] |
| `mimo-v2.5-asr`, `mimo-v2.5-tts*` | — | — | 8K | audio / text | text / audio [19] |

OpenRouter IDs: `xiaomi/mimo-v2.6-pro`, `xiaomi/mimo-v2.6-flash`, `xiaomi/mimo-v2.6-pro-ultraspeed`
(all created 2026-09-21 20:07 UTC, `context_length` 1,048,576, modality
`text+image+audio+video->text`) [28].

**Knowledge cutoff.** Not stated anywhere by Xiaomi (checked the model page, release note, HF card, model
overview) [1][13][19][24]. The only mention on the model page is a *sample system prompt* reading "Your
knowledge cutoff date is December 2024" (confirmed present on the page); that it is a stale template carried
over from the Dec-2025 V2 era rather than a spec is this author's inference (unverified as of 2026-09-24) [1].

**Release cadence.** V2-Flash Dec 2025 [51] → V2-Pro/Omni (deprecated 2026-06-30) [14] → V2.5 series
(OpenRouter created 2026-04-22) [28] → V2.5-Pro-UltraSpeed Jun 2026 [22] → V2.6 Sep 2026 [13]. Roughly a
major line every 4–5 months, with old lines deprecated ~2 months after replacement [14].

**Positioning.** As of this week MiMo-V2.6-Pro is the top open-weights model on the Artificial Analysis
Intelligence Index (46, #1 of the open-weights set, ahead of GLM-5.3 45, Kimi K3 44, GLM-5.3-Flash 42,
DeepSeek V4.1 Flash 39) [33][34], priced like a budget model ($0.435/$0.87 per 1M in/out, $0.0036 cached)
[1][3] but "notably slow and somewhat verbose" (45 tok/s, 3.1 s TTFT) [33]. Note that Xiaomi's chosen
comparator is no longer the frontier: the same AA leaderboard now tops out at Claude Opus 5.5 (58, max), Claude
Fable 5.1 (53) and GPT-6 Astra (53, max), so MiMo-V2.6-Pro's gap to the *current* frontier is ~7–12 index
points, not the ~5 implied by the Opus 5 comparison [56]. Xiaomi's own tables show it
trailing Claude Opus 5 on 10 of 14 shared evals (unverified as of 2026-09-24 — only 9 shared rows were
extractable from the HF card, on which Pro trails on 7: DeepSWE, ProgramBench, Toolathlon, TB 4.0, OSWorld,
ExploitBench; the 10/14 count could not be confirmed either way), with big gaps on Terminal-Bench 4.0
(34.9 vs 49.0) and ProgramBench (26.5 vs 37.0), while beating it narrowly on AutomationBench and
Terminal-Bench 2.1 [24][45].
The unusual part is the openness: a live public RL-training dashboard (mimo.xiaomi.com/rl/) that logged
every restart, plus MIT weights, environments and code [43][40][13].

## 2. Interfaces & surfaces

| Surface | Status | Notes |
|---|---|---|
| Consumer web chat | **MiMo Studio** (aistudio.xiaomimimo.com), Xiaomi-account sign-in; no published limits [46][39] | Page is JS-rendered; feature list not extractable [46]. |
| Desktop app | **MiMo Desktop** (invite-only beta announced 2026-09-08; free preview models named MiMo-X-Pro-Preview / MiMo-X-Flash-Preview during beta, to be switched to the V2.6 model names after beta; browser control; keyboard/mouse computer control "overseas version only"; smart routing; 99%/95% cache hit claims) [20][13] | "Beta desktop program ending in one week" per 09-22 release note [13]. OS list not stated [20]. |
| Mobile app | Not found — searched: mimo.xiaomi.com home, docs sitemap, release note. | |
| Browser/OS integration | Browser control + desktop control inside MiMo Desktop only [20]. | No extension found. |
| Voice | API: `mimo-v2.5-asr` (Chinese/English), `mimo-v2.5-tts`, `-voiceclone`, `-voicedesign` [19]; MiMo Code has `/voice` streaming input (needs `sox`, MiMo login) [36]. | TTS "free for a limited time" [3]. |
| CLI / agentic coding | **MiMo Code** (`@mimo-ai/cli`, MIT, 13.5k stars, a fork of OpenCode): `mimo` TUI, `mimo run "<prompt>"` headless, `mimo serve --port 4096` / `mimo attach <url>`, `--dangerously-skip-permissions`, persistent SQLite-FTS5 memory, checkpoints, subagents, `/goal` judge loop, `deep-research` and `fact-check` compose workflows [36][52]. | Also officially wired into Claude Code, Codex, OpenCode, OpenClaw, Hermes Agent, Cline, Kilo Code, Qwen Code, CodeBuddy, Chatbox, Cherry Studio [16]. |
| API + SDKs | OpenAI-compatible `https://api.xiaomimimo.com/v1` (chat/completions and `/v1/responses`), Anthropic-compatible `https://api.xiaomimimo.com/anthropic/v1/messages` [1][8][9]. No first-party SDK; docs use the `openai` Python SDK and curl [1][10]. | Auth header `api-key: $MIMO_API_KEY` or Bearer [9]. |
| MCP support | MiMo Code: "MCP server connections" configurable (inherited from OpenCode) [36]. Platform API: none found. | |
| Batch API | Yes — JSONL upload, `custom_id`, endpoints `/v1/chat/completions`, `/v1/responses`, `/anthropic/v1/messages`; 50% of real-time price; completion window 1–14 days, scheduled off-peak; 128 MB/file; files kept 30 days; base `https://batch-api-${region}.xiaomimimo.com/v1` [8]. | Not available for UltraSpeed [3]. Prerequisites: "Real-name verification must be completed before using Batch Inference", and batch "only deducts from your account's cash balance … not interchangeable with Token Plan package quotas" [8]; the account FAQ scopes real-name auth to mainland users ("Domestic users need to complete … real-name authentication before they can recharge") [17] — whether an overseas account clears the batch gate without it is unconfirmed. |
| Structured outputs | `response_format: {"type":"json_object"}` only; "only guarantees syntactically valid JSON"; no `json_schema` mode documented [11]. OpenRouter lists `structured_outputs`/`response_format` as supported params [28]. | Validate with `jsonschema` yourself [11]. |
| Tool use | Function calling on all V2.6 models; `tool_choice` auto/required (Xiaomi endpoint) [29]; parallel tool use toggle on Anthropic protocol [9]. | Must echo `reasoning_content` / `thinking` blocks back in multi-turn tool loops or get HTTP 400 [10][9]. |
| Web search tool | Built-in `web_search` tool (OpenAI protocol only): `force_search`, `max_keyword`, `user_location`; sources returned first in the stream with timestamps [12]. | $5 per 1,000 calls overseas (¥16 CN) + retrieved tokens at model rates [3][12]. |
| Computer-use / browser agent | Release note: "computer use agent functionality"; OSWorld-Verified 82.0 [13][24]. Productised only in MiMo Desktop [20]. | |
| Scheduled / automated tasks | None in the products; MiMo Desktop "smart scheduling" is task routing, not cron [20]. | |
| Memory | MiMo Code: cross-session memory (SQLite FTS5), `/dream` consolidation, checkpoints [36]. | |
| Projects / workspaces | MiMo Code project-level `.mimocode/mimocode.jsonc` config [36]; Token Plan Team edition (seats) [4]. | |
| Messaging (Telegram/Slack/…) | Not found — searched: docs sitemap (no messaging pages), MiMoClaw (it is a Kingsoft-Office document agent, China-only) [21]. | Reachable indirectly via OpenClaw/Hermes Agent integrations [16]. |
| IDE plugins | Via Cline, Kilo Code, CodeBuddy (VS Code / IDE) integration guides [16]. No first-party IDE extension found. | |

## 3. Headless / server automation fit

- **Non-interactive use on macOS/Linux.** Trivial via the OpenAI-compatible REST API (any HTTP client), or
  via `mimo run --dangerously-skip-permissions "<prompt>"` / `MIMOCODE_DANGEROUSLY_SKIP_PERMISSIONS=1`
  for the agent harness; `mimo serve` + `mimo attach` gives a client/server split for remote hosts [36].
  Install: `curl -fsSL https://mimo.xiaomi.com/install | bash` or `npm i -g @mimo-ai/cli` [36].
- **Auth modes.** (a) Pay-as-you-go API key `sk-…` (overseas accounts: email or Google/Facebook sign-up,
  USD settlement via "Waffo Console"; mainland accounts are separate and non-interoperable, require
  real-name auth) [17][6]. (b) Token Plan subscription key `tp-…` (individual) / `ttp-…` (team) on
  separate hosts `token-plan-{cn,sgp,ams}.xiaomimimo.com/{v1,anthropic}`; the two key types are not
  interchangeable [6][15]. (c) OAuth login inside MiMo Code to the Xiaomi platform, or OpenAI OAuth,
  or "Import from Claude Code" credentials [36]. (d) Batch API additionally requires completed real-name
  verification and bills only the cash balance, never Token Plan quota [8]; the account FAQ frames real-name
  as a mainland requirement [17], so confirm on the overseas console before designing around the batch lane.
- **Anthropic-protocol parameter limits.** `max_tokens` default and maximum 131,072 on all V2.6 models
  (32,768 on V2.5); `temperature` 0–1.5 (default 1.0); `top_p` 0.01–1.0 (default 0.95); both sampling
  params are overridden to defaults in thinking mode [9].
- **May subscriptions be used programmatically?** Explicitly **no** for generic automation. Token Plan
  quota "is only available for use in programming tools (such as OpenClaw, OpenCode, etc.), and it is
  prohibited to use it in the form of API calls for request behaviors in obvious non-coding scenarios
  such as automated scripts and custom application backends"; violations risk suspension and key
  blocking [5]. A scheduler that dispatches Claude Code/OpenCode coding jobs is a grey zone; a research/
  routing/Atlas job hitting the endpoint from Python is plainly outside the terms. No refunds once
  purchased [5]. MiMo Code's Use Restrictions add a ban on agents that "autonomously execute high-risk
  actions without appropriate human oversight" and on automating third-party platforms against their
  terms [37] — relevant to any trading-adjacent loop.
- **Rate limits (pay-as-you-go).** Account-level (summed over all keys per model): `mimo-v2.6-pro`
  100 RPM / 10M TPM; `mimo-v2.6-flash` 100 RPM / 10M TPM; UltraSpeed "customized, contact us";
  429 under load, retry with backoff recommended [7]. No published tier ladder. Token Plan per-plan rate
  limits are not published [5].
- **Sandboxing.** None server-side; MiMo Code runs tools locally with a permission prompt that you
  disable for headless use [36]. Batch API isolates work by JSONL file, one endpoint per file [8].
- **Structured event output.** REST: standard OpenAI SSE with `reasoning_content` streamed before
  `content` [10]; Anthropic protocol streams `message_start … message_stop` events with usage and stop
  reasons `end_turn|max_tokens|tool_use|content_filter|repetition_truncation` [9]. MiMo Code README
  mentions `--format` flags for `mimo run` but does not document a JSON event schema; since it is an
  OpenCode fork, OpenCode's `--format json` line-delimited events are the likely behaviour (unverified as of
  2026-09-24 — README re-fetch confirms `mimo run` and the skip-permissions flag/env var but no JSON event
  schema) [36].
- **Session resume.** MiMo Code: sessions persist in SQLite; memory + `checkpoint.md` are re-injected on
  resume; `mimo attach` reconnects to a running server [36]. Platform API is stateless.
- **Streaming.** `stream: true` on both protocols; UltraSpeed exists for latency-sensitive use at 10x
  price [3][9][10].
- **Thinking.** Enabled by default on all V2.6 text models; disable with
  `extra_body={"thinking":{"type":"disabled"}}`; in thinking mode `temperature`/`top_p` are forced to
  1.0/0.95 [10]. On the Anthropic path, keep prior `thinking` blocks in `messages` [9].
- **Gotcha:** prompt-cache *writes* are "limited-time free" [3] — budget for a future write charge.

## 4. Cost

**Consumer / subscription plans (Token Plan, overseas USD; CNY in brackets) [4][5]:**

| Plan | $/mo | Credits/mo | Xiaomi's "medium-to-complex tasks" estimate | Notes |
|---|---|---|---|---|
| Lite (individual only) | $6 (¥39) | 4.1B | ~200 | Annual = 12x quota at −12% ($63.36/yr) [5]; first purchase −12% [4] |
| Standard | $16 (¥99) | 11B | ~1,600 | also Team $16/seat |
| Pro | $50 (¥329) | 38B | ~5,600 | also Team $50/seat |
| Max | $100 (¥659) | 82B | ~12,800 | also Team $100/seat |

Credit burn per token: `mimo-v2.6-pro` 300 (input miss) / 2.5 (input cache hit) / 600 (output);
`mimo-v2.6-flash` 100 / 2 / 200; ASR 30M credits per audio hour; TTS free for now; 0.8x multiplier
00:00–08:00 Beijing time = **16:00–24:00 UTC** (Xiaomi's FAQ gives both) [4][18] — a scheduler on this
server can plan Token-Plan runs into that window, though the API pay-as-you-go path has no off-peak
discount other than Batch. Quota exhaustion suspends service (no overage) [4]. Programmatic use
prohibited (see §3) [5].

*Credit unit has already changed once.* The 2026-06-29 launch note listed Lite 60M / Standard 200M /
Pro 700M / Max 1,600M credits with per-model multipliers (1 token = 1 credit for mimo-v2-omni, 2 for
mimo-v2-pro at ≤256K, 4 for mimo-v2-pro at 256K–1M) [54]; the current page lists 4.1B / 11B / 38B / 82B
with the 300/600-per-token burn rates above [4]. Same dollar prices, different credit scheme — treat the
credit arithmetic in this section as a snapshot that may be rebased again.

Other paid consumer products: MiMoClaw ¥19.9/mo or ¥233.8/yr (introductory ¥14.9/mo); "Overseas
subscriptions are not yet available" [21]. UltraSpeed is not covered by Token Plan (unverified as of
2026-09-24 for V2.6 — source is the June 2026 V2.5-Pro-UltraSpeed note, "Token Plan is not supported for the
time being"; the current Token Plan page lists credit rates only for mimo-v2.6-pro and mimo-v2.6-flash, which
is consistent but not an explicit V2.6-UltraSpeed statement) [22][4]. A possibly cheaper high-speed path:
Xiaomi's 2026-09-08 note extended the MiMo-V2.5-Pro-UltraSpeed limited-time trial (~1000 tok/s, priced
3x V2.5-Pro) indefinitely for already-approved users at its limited-time price, after 66,000+
applications — but V2.5 IDs are scheduled for deprecation 2026-10-21, so do not build on it [55][14].

**API list prices (pay-as-you-go, overseas USD per 1M tokens) [3]:**

| Model | Input (cache miss) | Input (cache hit) | Output | Batch (miss / hit / out) |
|---|---|---|---|---|
| `mimo-v2.6-pro` | $0.435 | $0.0036 | $0.87 | $0.2175 / $0.0018 / $0.435 |
| `mimo-v2.6-flash` | $0.14 | $0.0028 | $0.28 | $0.07 / $0.0014 / $0.14 |
| `mimo-v2.6-pro-ultraspeed` | $4.35 | $0.036 | $8.70 | not supported |
| Web search tool | $5 / 1,000 calls (+ retrieved tokens at model rate) [3][12] | | | |
| `mimo-v2.5-asr` | $0.074 / audio hour | | | |

OpenRouter mirrors the same prices exactly ($0.435 / $0.87 / $0.0036 cached for Pro; $0.14 / $0.28 /
$0.0028 for Flash; $4.35 / $8.70 for UltraSpeed) on two providers, Xiaomi and DeepInfra (FP8) [28][29][30].
Cache-hit input is 121x cheaper than cache-miss input on Pro — this is the number behind the "~53x
cheaper cached pricing than Kimi K3" note in the brief (that ratio is from the Kimi doc, not
re-verified here) [3].

**Free tiers.** (1) OpenCode Zen: "MiMo-V2.6-Flash Free" and "MiMo-V2.5 Free" for a limited time while
feedback is collected; "collected data may be used to improve the model" [47]. (2) MiMo Code CLI: "free
experience of multimodal model comparable to Claude Sonnet 4.6 level without login" — Xiaomi's 2026-06-15 MiMo Code
release note names the built-in free channel model as MiMo-V2.5 ("Limited-Time Free Channel, Available Without
Registration"); quota not stated, and whether the channel moved to V2.6 is unconfirmed [38][53]. (3) MiMo Studio web chat, sign-in required, limits unpublished [46]. (4) MiMo Desktop beta:
free preview models, invite-only, beta ending [20][13]. (5) TTS models and prompt-cache writes free for a
limited time [3]. (6) Earlier "Agent Framework Call Free Trial" for V2 ended 2026-04-02 [23]. New-account
API credits: not found (unverified as of 2026-09-24 — account FAQ confirms no starter credits are documented;
the promotions page is JS-rendered, so a promo cannot be ruled out) — searched: pay-as-you-go page, account
FAQ, promotions/refer page.

**Monthly cost estimate — 150k input + 15k output per job.** Assumptions: (A) no cache hits; (B) 70% of
input served from prompt cache (realistic for agent loops that re-send a long prefix); output never
cached; Batch = 50% of real-time; Token Plan credits at the rates above with no off-peak bonus.

Per-job API cost: Pro A = 150k×$0.435 + 15k×$0.87 = **$0.0783**; Pro B = 45k×$0.435 + 105k×$0.0036 +
15k×$0.87 = **$0.0330**; Flash A = **$0.0252**; Flash B = **$0.0108**; Pro Batch A = **$0.0392**.
Per-job credits: Pro A = 150k×300 + 15k×600 = 54M; Flash A = 18M.

| Jobs / mo | (a) Token Plan (cheapest tier that covers it, no-cache) | (b) API Pro (A / B) | (b) API Flash (A / B) | (b) Pro Batch (A) |
|---|---|---|---|---|
| 10 | Lite $6 (0.54B of 4.1B credits used; Flash 0.18B) — **but terms forbid this use** [5] | $0.78 / $0.33 | $0.25 / $0.11 | $0.39 |
| 100 | Pro jobs: Standard $16 (5.4B of 11B); Flash jobs: Lite $6 (1.8B of 4.1B) — same caveat | $7.83 / $3.30 | $2.52 / $1.08 | $3.92 |
| 1000 | Pro jobs: Max $100 covers 1,518 jobs (54B of 82B); Flash jobs: Standard $16 covers 611, Pro $50 covers 2,111 | $78.30 / $33.00 | $25.20 / $10.80 | $39.20 |

Reading: at these list prices a subscription buys almost nothing over pay-as-you-go — 1B credits costs
$1.46 (Lite) to $1.22 (Max) and 1M Pro output tokens = 0.6B credits, i.e. $0.73–$0.88 vs $0.87 API — so
the Token Plan is at best a 0–16% discount and is contractually unusable for a scheduler [4][5]. The
API path is the one that fits this server; 1,000 Pro jobs a month is under $80 even with zero caching.

## 5. Strengths & weaknesses per reviews

**Benchmarks.**
- Artificial Analysis Intelligence Index (v4.3.2): MiMo-V2.6-Pro 46 — #1 open-weights; index cost per
  task $0.13 vs Claude Opus 5 $5.86 (51), GPT-6 Astra low $0.82 (46), Grok 4.7 $3.74 (46), Kimi K3 $2.00
  (44) [33][45]. Open-weights table: GLM-5.3 45 ($0.9 blended, 58 tok/s), Kimi K3 44 ($2.3), GLM-5.3-Flash
  42 ($0.1, 43 tok/s), DeepSeek V4.1 Flash 39 ($0.2, 232 tok/s), MiMo-V2.6-Pro 46 ($0.2, 45 tok/s) [34].
  AA: "amongst the leading models in intelligence and reasonably priced … also notably slow and somewhat
  verbose" (140M output tokens to run the index) [33]. **MiMo-V2.6-Flash is not yet on AA** — searched:
  /models/mimo-v2-6-flash (+ -reasoning, -rl slugs), open-source table [34].
- Xiaomi's own card (Pro vs Claude Opus 5 vs GPT-5.6 Sol): DeepSWE v1.1 71.9 / 74.0 / 73.0; ProgramBench
  26.5 / 37.0 / 25.0; AutomationBench 53.1 / 50.3 / 45.8; Toolathlon-Verified 76.9 / 80.6 / 74.9;
  Terminal-Bench 4.0 34.9 / 49.0 / 39.9; Terminal-Bench 2.1 89.9 / 89.1 / 88.8; OSWorld-Verified 82.0 /
  83.4 / 83.0; CyberGym 94.0 (no comparator scores given); ExploitBench 47.9 / 70.0 / 78.5 [24][45]. Flash: DeepSWE 67.9, Toolathlon 73.6,
  TB 2.1 87.6, CyberGym 95.1 [25]. 9B distill: SWE-Verified 61.1, SWE-Pro 44.6, TB 2.1 37.1 [26].
- SWE-bench Verified / Terminal-Bench official leaderboards: Not found — searched: swebench.com and
  tbench.ai/leaderboard (JS-rendered; no MiMo rows in HTML). GPQA / HLE / LMArena for V2.6: not
  published; LMArena text board (2026-09-13) lists `mimo-v2.5-pro` at rank 44 (1467) and `mimo-v2.5` at
  96 (1434) vs top 1506 [35]. OpenRouter rankings page (usage through 2026-09-23) shows MiMo-V2.6-Pro in
  position 10 (unverified as of 2026-09-24 — the page is JS-rendered and a re-fetch returned what reads like
  intelligence scores rather than token usage, so the position itself is unconfirmed); the token counts were
  not extractable from the page (unverified count) [31].

**Professional / expert reviews.**
- Sebastian Raschka: the architecture is deliberately simple (GQA + 128-token sliding-window attention);
  gains come from the RL recipe — agentic-trace graders, 25,088 trajectories per batch — "most of the
  progress still comes from the data and post-training recipe improvements" [42].
- kingy.ai hands-on in OpenCode (bug fix, multi-file feature, data analysis): Pro 23/23 checks for ~$0.03
  vs Opus 5 23/23 for ~$1.03; Flash 21/23 for free. Verdict: comparable on routine coding, "trails
  frontier models significantly on Terminal-Bench 4.0, exploitation benchmarks, and long-horizon agent
  tasks", "somewhat verbose" [45][46].
- Forkast/The New Stack framed the public RL dashboard as unprecedented openness [43][50]; SiliconANGLE
  relays Xiaomi's "1/20 to 1/60 the price of comparable Western models" claim [44][13].

**Community (Hacker News, 1,123-point launch thread and AA thread) [40][41][48].**
- Praise centres on transparency ("They logged every restart with a reason" — tancop; the dashboard is
  "an incredible learning and teaching tool" — rao-v) [40].
- Price: "incredibly cheap, given its cache rates will remain $0.0036 per million" (ignoramous) [41].
- Scepticism of the AA ranking: users questioned why it scores 46 vs DeepSeek-V4.1 at 39 when DeepSeek
  "sometimes surpasses it" (egeres); "the main AA benchmark keeps changing" (SyneRyder) [41].
- Speed: "still much slower than leading models" (dom96) [41]. Prior-gen behaviour: "Mimo2.5 is really
  good, but tended to loop too much" (segmondy) [41].
- Openness caveat: the dashboard shows a "Claude Distill Requests: hidden" panel and numbers that reset
  on refresh, prompting questions about distillation from proprietary models and data authenticity [43].

**Best at:** cost-per-unit-intelligence for agentic coding and tool-use (AutomationBench, TB 2.1, DeepSWE),
long-context (1M) omnimodal input, open weights + MIT, prompt-cache economics [24][33][3].
**Weak at:** latency/throughput (45 tok/s, 3.1 s TTFT) [33], hardest terminal/long-horizon and
exploit tasks [24][45], verbosity [33], no `json_schema` mode [11], regional account split [17].
**Reliability:** Xiaomi's OpenRouter endpoint showed 99.2–99.97% uptime over 30 m/5 m/24 h at check
time, DeepInfra's 81.7–90.2% [29][30] (re-checked 2026-09-24: Xiaomi 99.4%/99.9%, DeepInfra 83.9% on Pro and 88.7%/69.4% on Flash, with the DeepInfra endpoints carrying status -2, i.e. deranked — these are live values, not a fixed spec); docs warn of 429s under load [7]. Model deprecations are fast (V2.5
gone 2026-10-21, ~1 month after V2.6) [14] — pin IDs and watch the deprecation page.
**Controversies:** the hidden "Claude distill" counter [43]; AA index weighting debates [41]; Chinese
data-jurisdiction concerns typical of the category (overseas vs mainland data planes are separate) [17].

## 6. Finance / trading relevance

- **Real-time data:** only via the built-in `web_search` tool (news/products/weather, timestamps on
  sources, $5/1K calls) [12][3]. No market-data connectors, tickers, or finance products found —
  searched: docs sitemap (no finance pages), home page product list [39], MiMoClaw (office documents,
  China-only) [21].
- **Sentiment sources:** none native; web search only [12].
- **Restrictions:** platform terms/privacy pages are JS-rendered and could not be read (Not found —
  searched: /docs/en-US/quick-start/terms/terms-of-service, /privacy-policy; re-checked 2026-09-24, the
  terms URL still renders only a title — unverified as of 2026-09-24). MiMo Code's Use
  Restrictions prohibit agents that "autonomously execute high-risk actions without appropriate human
  oversight" and automation of third-party platforms against their terms [37] — consistent with Atlas's
  no-live-order rule, but the doc must be re-read before any order path is ever considered.
- **Data retention / training on the paid API: UNKNOWN — treat as a blocker for sensitive Atlas data.**
  The free routes are partially covered (OpenCode Zen: "collected data may be used to improve the model"
  [47]), but nothing readable states whether Xiaomi's own pay-as-you-go API retains inputs or trains on
  them; the terms/privacy pages could not be read (above). Until a human reads Xiaomi's terms, send this
  vendor only public or already-published material (filings, transcripts, public research), never
  positions, ledgers, credentials, or unpublished Atlas theses.
- **Fit:** cheap, 1M-context reasoning over filings/transcripts/CSVs and adversarial review of Atlas
  research at ~$0.03–0.08 per job [3]; audio input could ingest earnings calls directly [1]. Not a data
  source, and a China-jurisdiction vendor for anything sensitive.

## 7. Integration recipe for our server

**Recommended path:** pay-as-you-go API key (overseas account, USD) [17] hitting
`https://api.xiaomimimo.com/v1` with the `openai` Python SDK — or OpenRouter (`xiaomi/mimo-v2.6-*`,
identical prices, one key for all vendors, `provider` routing to prefer the Xiaomi endpoint) [28][29].
Do **not** buy a Token Plan for the scheduler (terms) [5]. Keep `mimo-v2.6-flash` as the default bulk
lane and `mimo-v2.6-pro` for review/research; Batch API for nightly non-urgent jobs (50% off, 1–14 day
window) [8][3]. Store keys in `.env` under a new name (e.g. `MIMO_API_KEY`) — never `ANTHROPIC_API_KEY`.

```python
# src/runner/providers/mimo.py (sketch) — OpenAI-compatible, thinking on, JSON mode
import os, json
from openai import OpenAI

client = OpenAI(api_key=os.environ["MIMO_API_KEY"],
                base_url="https://api.xiaomimimo.com/v1")   # or https://openrouter.ai/api/v1

def mimo_call(messages, model="mimo-v2.6-flash", tools=None, json_mode=False, think=True):
    kw = dict(model=model, messages=messages, max_completion_tokens=8192, stream=False,
              extra_body={"thinking": {"type": "enabled" if think else "disabled"}})
    if tools: kw["tools"] = tools; kw["tool_choice"] = "auto"
    if json_mode: kw["response_format"] = {"type": "json_object"}   # syntactic JSON only [11]
    r = client.chat.completions.create(**kw)
    msg = r.choices[0].message
    # REQUIRED: echo reasoning_content back on the next turn of a tool loop, else HTTP 400 [10]
    assistant = {"role": "assistant", "content": msg.content or "",
                 "reasoning_content": getattr(msg, "reasoning_content", None)}
    if msg.tool_calls:
        assistant["tool_calls"] = [tc.model_dump() for tc in msg.tool_calls]
    return r, assistant
```

Claude-Code-harness variant (for coding jobs only, pay-as-you-go key) — set per job, not globally, so
the Max-subscription lane is untouched [15]. The Anthropic-protocol endpoint accepts `max_tokens` up to
131,072 on V2.6 models (32,768 on V2.5), `temperature` 0–1.5 (default 1.0) and `top_p` 0.01–1.0 (default
0.95), both forced to defaults while thinking is on [9]:

```bash
ANTHROPIC_BASE_URL=https://api.xiaomimimo.com/anthropic \
ANTHROPIC_AUTH_TOKEN=$MIMO_API_KEY \
ANTHROPIC_MODEL=mimo-v2.6-pro ANTHROPIC_DEFAULT_SONNET_MODEL=mimo-v2.6-pro \
ANTHROPIC_DEFAULT_OPUS_MODEL=mimo-v2.6-pro ANTHROPIC_DEFAULT_HAIKU_MODEL=mimo-v2.6-flash \
claude -p "<task>" --output-format stream-json --dangerously-skip-permissions
```

Batch lane: write JSONL (`custom_id`, `method`, `url: /v1/chat/completions`, `body`), upload with
`client.files.create(purpose="batch")`, `client.batches.create(endpoint="/v1/chat/completions",
completion_window="24h")` against `https://batch-api-${region}.xiaomimimo.com/v1`; poll; results kept
30 days [8]. Before relying on this lane: batch requires completed real-name verification and bills the cash
balance only [8] — verify on the overseas console whether the real-name gate applies to non-mainland
accounts (the account FAQ says it is a mainland requirement [17]).

**Task-class fit here:**
- Research (long-doc synthesis, 1M context, web search tool): good — Pro; use `max_keyword` to cap
  search cost [12].
- Coding: Flash for routine fixes (kingy 8/8 bug fix) [45]; Pro for multi-file; expect weaker results on
  long-horizon terminal tasks than Fable/Opus [24].
- Code review / adversarial review of Atlas outputs: good value as a *second* reviewer (different lineage
  from Claude), never the sole INV-13 gate.
- Chat/Telegram front door: no — 3 s TTFT and 45 tok/s [33]; UltraSpeed fixes latency at 10x price [3].
- Classification / routing: Flash in JSON mode at ~$0.01/job (B) — but validate schema locally [11].
- Trading research: yes for reading/ranking; no data access beyond web search [12].

**Gotchas:** lowercase model IDs [13]; `reasoning_content`/`thinking` must be echoed in tool loops
[10][9]; thinking mode ignores `temperature`/`top_p` [10]; `json_object` is not schema-enforced [11];
account-level 100 RPM shared across keys [7]; mainland vs overseas keys/base URLs are different planes
[17]; V2.5 IDs die 2026-10-21 [14]; DeepInfra route on OpenRouter had ~82–90% uptime at check time —
pin `provider.order: ["xiaomi"]` [29]; free/Zen routes may train on your data [47]; cache-write pricing
is a limited-time zero [3]; Xiaomi's own OpenRouter endpoint caps completion at 131,072 tokens [29];
batch needs real-name verification and cash balance [8]; paid-API data retention/training policy is
unreadable — no sensitive data (§6).

## 8. Verdict

1. MiMo-V2.6-Pro is, this week, the strongest open-weights model on Artificial Analysis and costs
   $0.435/$0.87 per 1M with $0.0036 cached input — a generation behind the frontier (AA 46 vs Claude Opus
   5.5 58 / Claude Fable 5.1 53 / GPT-6 Astra 53, a 7–12 point gap [56]) at 1/20–1/60 the price of
   Opus/Astra by Xiaomi's framing and ~45x cheaper per AA task than Opus 5 in AA's own accounting [33][45].
2. It is slow (45 tok/s, 3 s TTFT), verbose, and clearly behind Claude Opus 5 — itself no longer the
   frontier — on the hardest terminal, exploit and long-horizon benchmarks [33][24].
3. For this server the only compliant path is pay-as-you-go API (direct or OpenRouter); the $6–$100
   Token Plans prohibit "automated scripts and custom application backends" and barely undercut API
   list price anyway [5][4].
4. Flash (`$0.14/$0.28`) is a credible bulk lane against GLM-5.3-Flash / DeepSeek V4.1 Flash on price,
   but it is not yet independently scored and DeepSeek Flash is ~5x faster [34][3].
5. Watch-outs: China data jurisdiction and an unreadable paid-API data-retention policy (no sensitive
   Atlas data until a human reads the terms), aggressive deprecation cadence, the hidden "Claude distill"
   counter, a credit unit that has already been rebased once, batch's real-name gate, and that structured
   output is JSON-mode only.

Fit scores (1–10): research **7**, coding/agentic **7**, cost efficiency **9**, automation friendliness
**6** (great API, but subscription terms and no schema mode), trading research **5**.

## 9. Sources

All accessed 2026-09-24.

1. https://mimo.mi.com/models/en-US/mimo-v2.6-pro
2. https://mimo.mi.com/models/en-US/mimo-v2.6-flash
3. https://mimo.mi.com/docs/en-US/price/pay-as-you-go
4. https://mimo.mi.com/docs/en-US/price/token-plan
5. https://mimo.mi.com/docs/en-US/tokenplan/Token%20Plan/subscription
6. https://mimo.mi.com/docs/en-US/tokenplan/Token%20Plan/quick-access
7. https://mimo.mi.com/docs/en-US/api/guidance/rate-limit
8. https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/batch-api
9. https://mimo.mi.com/docs/en-US/api/chat/anthropic-api
10. https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/deep-thinking
11. https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/structured-output
12. https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/tool-calling/web-search
13. https://mimo.mi.com/docs/en-US/news/latest/v2-6
14. https://mimo.mi.com/docs/en-US/updates/deprecate
15. https://mimo.mi.com/docs/en-US/tokenplan/integration/claudecode
16. https://mimo.mi.com/docs/en-US/tokenplan/integration/tools-overview
17. https://mimo.mi.com/docs/en-US/quick-start/faq/account
18. https://mimo.mi.com/docs/en-US/quick-start/faq/token-plan/Usage%26Quota
19. https://mimo.mi.com/docs/en-US/quick-start/summary/model
20. https://mimo.mi.com/docs/en-US/news/latest/mimo-desktop
21. https://mimo.mi.com/docs/en-US/news/latest/mimoclaw
22. https://mimo.mi.com/docs/en-US/news/latest/1000tps
23. https://mimo.mi.com/docs/en-US/news/latest/free-trial-extension
24. https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Pro-RL
25. https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Flash-RL
26. https://huggingface.co/XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B
27. https://huggingface.co/XiaomiMiMo
28. https://openrouter.ai/api/v1/models (filtered for `xiaomi/`; created timestamps, pricing, params)
29. https://openrouter.ai/api/v1/models/xiaomi/mimo-v2.6-pro/endpoints
30. https://openrouter.ai/api/v1/models/xiaomi/mimo-v2.6-flash/endpoints
31. https://openrouter.ai/rankings
32. https://openrouter.ai/xiaomi
33. https://artificialanalysis.ai/models/mimo-v2-6-pro
34. https://artificialanalysis.ai/models/open-source
35. https://arena.ai/leaderboard/text
36. https://github.com/XiaomiMiMo/MiMo-Code (README, raw: https://raw.githubusercontent.com/XiaomiMiMo/MiMo-Code/main/README.md)
37. https://raw.githubusercontent.com/XiaomiMiMo/MiMo-Code/main/USE_RESTRICTIONS.md
38. https://mimo.xiaomi.com/coder
39. https://mimo.xiaomi.com/
40. https://news.ycombinator.com/item?id=49792730 (MiMo v2.6 launch thread)
41. https://news.ycombinator.com/item?id=49796660 (Artificial Analysis thread)
42. https://sebastianraschka.com/blog/2026/mimo-v2-6-pro-architecture-training-notes.html
43. https://forkast.news/xiaomi-mimo-v2-6-breaks-cover-a-1t-class-chinese-lab-trains-in-public/
44. https://siliconangle.com/2026/09/22/xiaomi-introduces-mimo-v2-6-series-open-source-ai-model-family/
45. https://kingy.ai/blog/mimo-v2-6-pro-benchmarks-specs-comparison/
46. https://kingy.ai/blog/mimo-v2-6-pro-free-access-pricing-setup/
47. https://opencode.ai/docs/zen/
48. https://hn.algolia.com/api/v1/search?query=MiMo-V2.6&tags=story
49. https://news.google.com/rss/search?q=Xiaomi+MiMo-V2.6&hl=en-US&gl=US&ceid=US:en (press index: VentureBeat, WinBuzzer, eWeek, TNW, alphaXiv — headlines only)
50. https://thenewstack.io/xiaomi-mimo-vs-6-open-source/ (headline/byline only; body not fetched)
51. https://mimo.xiaomi.com/blog (MiMo-V2-Flash post, 2025-12-16)
52. https://github.com/XiaomiMiMo
53. https://mimo.mi.com/docs/en-US/news/latest/mimocode (MiMo Code release note, 2026-06-15)
54. https://mimo.mi.com/docs/en-US/news/latest/token-plan-release (Token Plan launch note, 2026-06-29)
55. https://mimo.mi.com/docs/en-US/news/latest/beta-extended (V2.5-Pro-UltraSpeed trial extension, 2026-09-08)
56. https://artificialanalysis.ai/leaderboards/models (Intelligence Index leaderboard, fetched 2026-09-24)

## Verification log (2026-09-24)

**Corrections applied:** 6 total — 0 critical, 0 major, 6 minor (MiMo Code free-channel model named as
V2.5 per the 06-15 release note; HN quote wording "will remain"; CyberGym/ExploitBench comparator columns;
MiMo Desktop beta date and preview model names; Token Plan first-purchase discount citation moved to [4];
OpenRouter uptime figures re-checked with live values and DeepInfra derank status).

**Claims re-verified (source):**
- Batch API requires real-name verification and bills cash balance only, never Token Plan quota — [8]
  batch-api page; real-name scoped to mainland users — [17] account FAQ.
- Token Plan credit denominations rebased: 60M/200M/700M/1,600M with 1x–4x multipliers at the
  2026-06-29 launch — [54]; now 4.1B/11B/38B/82B at 300/600 per token — [4].
- Current AA frontier: Claude Opus 5.5 58, Claude Fable 5.1 53, GPT-6 Astra 53 — [56].
- V2.5-Pro-UltraSpeed trial extended indefinitely for approved users at 3x V2.5-Pro price, ~1000 tok/s,
  66,000+ applications, note dated 2026-09-08 — [55].
- Anthropic-protocol limits: max_tokens 131,072 (V2.6) / 32,768 (V2.5), temperature 0–1.5 default 1.0,
  top_p 0.01–1.0 default 0.95 — [9].
- MiMoClaw ¥14.9/mo introductory, ¥19.9/mo standard, overseas not available — [21].
- Off-peak window 00:00–08:00 Beijing = 16:00–24:00 UTC, 0.8x — [18].
- MiMo Code free channel = MiMo-V2.5, no registration — [53].

**Stale / unverified flags left in place (all marked "unverified as of 2026-09-24"):** §1 "10 of 14
shared evals" (only 9 rows extractable, Pro trails on 7); §1 knowledge-cutoff template interpretation;
§1 exact release date (09-21 UTC vs 09-22 Beijing); §3 MiMo Code `--format json` event schema; §4
UltraSpeed-not-in-Token-Plan for V2.6; §4 new-account API credits; §5 OpenRouter usage rank 10; §6
platform terms / paid-API data-training policy (still unreadable).

**Fact-checker's overall quality rating:** good.
