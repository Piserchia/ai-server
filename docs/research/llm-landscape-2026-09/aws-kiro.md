# AWS Kiro / Amazon Q Developer (and Windsurf) — research (as of 2026-09-24)

Scope note: three products are covered because they have converged. **Amazon Q Developer** (IDE plugins, `q` CLI) is
being retired into **Kiro** [28][29][30]. **Windsurf** was acquired by Cognition (July 2025) and on 2026-06-02 was
rebranded **Devin Desktop**; `windsurf.com` now 308-redirects to `devin.ai` [36][40]. Where the three differ it is
called out; otherwise "Kiro" is the primary subject and "Devin Desktop/CLI" is the secondary comparator.

Research caveat: the web-search budget for this session was exhausted before this task started, so every fact below
comes from direct fetches of vendor docs, vendor blogs, HN/Google-News indexes, and a handful of named articles. Reddit
was unreachable. Where a page 404'd or a number was not printed, it is marked "Not found" or "(unverified)".

---

## 1. Snapshot

**Company / product.** Kiro is AWS's agentic developer platform (IDE fork of Code OSS, CLI, Web, Mobile, Crew). It
launched July 2025 as an "agentic AI IDE" [54], hit its one-year mark in July 2026 [14], and has absorbed Amazon Q
Developer: "The Q CLI has become the Kiro CLI" [29]; Q Developer IDE plugins reach end of support on
**2027-04-30** with migration guidance pointing to Kiro [30]. Q Developer Pro customers keep their benefits when
signing in to Kiro with the same credentials [2] (which Kiro tier/credits/API-key eligibility that maps to is unverified as of 2026-09-24 — no vendor page states it).

**Model lineup on Kiro (2026-09-24)** — Kiro is a multi-vendor router, not a model vendor. Exact names as printed on the
models page [6] (Kiro does not publish API-style IDs; the CLI agent config uses slugs like `"claude-sonnet-5"` [24]):

| Model (Kiro name) | Provider | Credit multiplier | Context | Status / region |
|---|---|---|---|---|
| Auto (Kiro Router) | Kiro | 1x baseline ("X credits") [1] | varies | Active; never routes to experimental models |
| Claude Fable 5.1 (Preview) | Anthropic | **6x** | 1M | Experimental; **Enterprise-only** — rolling out to Kiro Enterprise orgs with model governance enabled (admin adds it to the approved list); not on individual Pro/Pro+/Pro Max/Power seats; us-east-1 only [6][13][59] |
| Claude Opus 5 | Anthropic | **2.2x** | 1M | Active, us-east-1 + eu-central-1 |
| Claude Opus 4.8 / 4.7 / 4.6 / 4.5 | Anthropic | not printed | 4.8: 1M ctx, 128K out | Active |
| Claude Sonnet 5 / 4.6 / 4.5 / 4.0 | Anthropic | **1.3x** (printed only for Sonnet 5 on the models page and Sonnet 4.6 in the FAQ; 4.5/4.0 not printed) | not printed | Active; Sonnet 4.5 is the only Claude on Free (unverified as of 2026-09-24 — the models page also says Auto on Free gives "Claude Sonnet-class quality or better"; the exact Free model set is not enumerated) [1][2][6] |
| Claude Haiku 4.5 | Anthropic | not printed | not printed | Active |
| GPT-5.6 Sol / Terra / Luna | OpenAI | 4.4x / 2.2x / 1.1x up to 272K; doubles above 272K | 1M (since 2026-09-14) | Experimental |
| MiniMax M2.5 / M2.1 | MiniMax | 0.25x / 0.15x | not printed | Active / Experimental |
| GLM-5 | Z.ai | 0.5x | 200K | Active |
| DeepSeek 3.2 | DeepSeek | 0.25x | not printed | Experimental |
| Qwen3 Coder Next | Qwen | 0.05x | 256K | Experimental |

Knowledge cutoffs are not printed by Kiro; for the Claude models they are Anthropic's (e.g. Sonnet 5: January 2026 per
the Bedrock model card [34]). Modalities: text + image input, text output, per the same Bedrock cards [34].

**Devin Desktop / CLI lineup.** Claude, OpenAI, Google, SpaceXAI (`grok`), Cognition (SWE-2, SWE-1.7, SWE-1.6 Fast), DeepSeek, Kimi, GLM; short
names `opus`, `sonnet`, `swe`, `codex`, `gemini` resolve to the latest in-family [41][45]. SWE-2 (2026-09-10) is a
Cognition fine-tune on Kimi K3 (2.8T params) with medium/high/max effort [39]. No per-model quota multipliers are
published (Not found — searched: docs.devin.ai/cli/models.md, admin/billing/self-serve.md, admin/billing/usage.md).

**Release cadence.** Very fast: Kiro CLI ships roughly weekly (2.22.0 on 09-16, 2.22.1 09-16, 2.23.0 09-21, 2.23.1
09-23) [13]; new models land within days of upstream (Opus 5 07-24, Sonnet 5 07-01, GPT-5.6 07-14, Fable 5.1 preview
09-16) [13][14]; Kiro Web reached General Availability on 2026-09-01 and Kiro Crew 0.6.0 shipped 2026-09-05 [13]. Cognition ships a model or harness change every few weeks (SWE-Check 04-14, SWE 1.6 06-19, SWE-1.7 07-08, Devin
Desktop 06-02, SWE-2 09-10, Fusion 09-11) [38][53].

**Positioning.** Kiro sells "spec-driven development" (requirements → design → tasks) plus one agent harness shared by
IDE/CLI/Web/Mobile, priced in vendor-neutral "credits" so you can pick Claude, GPT or open-weight models on one
$0–$200 seat [1][3]. Its 2026 differentiators are governance (SMT-solver "Requirements Analysis" on specs [52]),
Kiro Web scheduled automations [16], and Kiro Crew — an Apache-2.0 open-source, self-hosted persistent agent with
Telegram/Slack/Discord channels, cron jobs and memory, driven through `kiro-cli` over ACP [19][20]. Devin Desktop is
positioned as an "agent command center" IDE with a first-party model (SWE-2) that Cognition claims is 64% cheaper than
Fable 5.1 at comparable coding performance [39][40].

---

## 2. Interfaces & surfaces

**Kiro**
- **IDE**: Code OSS fork (v1.1, 2026-09-14, ARM64 Windows/Linux builds) [13]; also Powers/agents from the IDE [23].
- **CLI**: `kiro-cli` (macOS/Linux/Windows; `curl -fsSL https://cli.kiro.dev/install | bash`) with interactive TUI,
  headless mode, fullscreen chat, voice mode (local Whisper), ACP server mode, hooks, custom agents, MCP [4][13].
- **Web**: `app.kiro.dev`, cloud sessions against GitHub/GitLab repos, interactive / spec / autonomous modes; IDE and CLI
  can attach to cloud sessions; **General Availability since 2026-09-01** [13]; Configuration Sync (also 09-01) can carry cloud
  config (steering files, custom agents, Skills, Powers, Hooks) into new local IDE/CLI sessions while keeping cloud content
  out of local directories [13]; **paid tiers only (Pro/Pro+/Pro Max/Power)**; "us-east-1 only" is printed on the Web docs
  page directly after the AWS Identity Center prerequisite, so whether it is universal or Identity-Center-only is
  (unverified as of 2026-09-24) [15]; "Kiro never merges changes automatically" [15].
- **Mobile**: iOS app (2026-06-17), Preview — early access via Apple TestFlight (request required); no Android [3][14].
- **Crew**: self-hosted personal agent (desktop apps + web dashboard + CLI), channels: Slack, Discord, Telegram, Teams,
  Webex, WeCom, WeChat, WhatsApp, Feishu, iMessage; cron scheduling; heartbeat monitoring; memory/skills [17][19][20].
  Crew 0.6.0 (2026-09-05): selectable agent harness (default `kiro-cli`; Claude Code, Codex or KAS via Settings > Developer
  > Agent Backend, Preview), Remote Crews (chat on a connected crew from the sidebar), Python 3.12 now required; the repo
  also ships a Docker image `ghcr.io/kirodotdev/kirocrew:stable` and requires Node.js 22+ (24 LTS recommended) on
  macOS/Linux [13][20].
- **API + SDKs**: **none.** Kiro exposes no public REST/SDK; programmatic access is the CLI (headless or ACP JSON-RPC
  over stdio) [5][10]. There is no OpenAI- or Anthropic-compatible endpoint. (For an API you go to Amazon Bedrock,
  which is a separate metered product — see §4.)
- **MCP**: client support in IDE and CLI (`kiro-cli mcp add|remove|list|import|status`), `--require-mcp-startup` for
  CI [4][8].
- **Batch API / structured outputs**: not applicable (no API). `--output-format stream-json` gives JSONL events [5].
- **Tool use / computer use / browser agent**: built-in tools + MCP; no first-party browser/computer-use agent found
  (Not found — searched: kiro.dev/docs/, /docs/powers/).
- **Scheduled / automated tasks**: Kiro Web Automations (hourly/daily/cron in UTC, ≤5 schedules per automation, prompt
  ≤10,000 chars, output = PR per repo) [16]; Kiro Crew crons (`crons.json`, timezone-aware) [18][20]; hooks (11+ triggers
  incl. PreToolUse/PostToolUse/AgentStop, 60 s default command timeout) [22].
- **Memory / projects**: steering files + specs per workspace; Crew adds persistent cross-session memory and
  self-synthesised skills [3][20].
- **Messaging**: only via Crew (list above). No first-party Telegram bot for the IDE/CLI itself.
- **IDE plugins**: Kiro's harness reaches JetBrains/Zed via ACP [10]; Q Developer plugins for VS Code/JetBrains/Visual
  Studio/Eclipse remain until 2027-04-30 [30]; Q Developer also lives in the AWS Console, docs site, and Slack/Teams chat
  apps [28].

**Devin Desktop / CLI**
- Desktop IDE (ex-Windsurf, "fully backwards-compatible with Windsurf"), Windsurf plugin for JetBrains still available
  [36][40]; `devin` CLI (`curl -fsSL https://cli.devin.ai/install.sh | bash` or `brew install --cask devin-cli`)
  [42]; `devin acp` runs Devin as an ACP server over stdio for Zed/Devin Desktop-style editors, and `devin migrate hooks`
  converts Windsurf `.windsurf/hooks.json` to `.devin/hooks.v1.json` [41]; Devin Web/cloud sessions with SSH; Slack/Teams integrations; MCP (stdio/http/sse); a real REST API
  (`POST https://api.devin.ai/v3/organizations/$ORG/sessions`) whose plan availability and ACU price were not found
  [46][57].

---

## 3. Headless / server automation fit

**Kiro CLI headless (official, documented path)** [5][7][8]:
- `kiro-cli chat --no-interactive "prompt"` or `printf '%s\n' "prompt" | kiro-cli chat --no-interactive`.
- **Auth**: "Headless mode requires an API key set as the `KIRO_API_KEY` environment variable"; keys (`ksk_…`) are
  minted in the web console and "only available for Kiro Pro, Pro+, Pro Max, and Power subscribers" [5][7]. Interactive
  sign-in options are GitHub, Google, AWS Builder ID, IAM Identity Center; remote machines use a device-code flow
  (`kiro-cli login --use-device-flow`) [7][8]. `kiro-cli login` flags relevant to a scripted setup: `--license pro|free`
  (`pro` = Identity Center, `free` = Builder ID/Google/GitHub), `--social google|github`, `--identity-provider <url>`,
  `--region <aws-region>` (both Identity Center only), `--use-device-flow` [8]. Documented precedence: (1) active browser session, (2) `KIRO_API_KEY`,
  (3) prompt [7]. Free tier has no API keys, so Free cannot run headless.
- **Terms**: the vendor *ships* API keys "for CI/CD pipelines" [7][26] — automation is the intended use, not a grey
  area. The FAQ points to "AWS Service Terms Section 50.10" for output indemnity [2], but a fetch of the Service Terms
  found "Kiro" only in §1.24 (generative-AI features list) — the section numbering has likely moved; no clause
  prohibiting programmatic/headless use was found (Not found — searched: aws.amazon.com/service-terms, kiro.dev/terms,
  kiro.dev/docs/enterprise/team-subscription). Seats are per-developer ("Each developer requires their own
  subscription") [2].
- **Permissions/sandboxing**: `--trust-all-tools` or `--trust-tools=read,grep,write`; custom agents carry
  `tools`/`excludedTools`/`permissions` [5][24]; hooks can block a tool with exit code 2 [9][22]. No OS-level sandbox;
  you supply it (a dedicated user, a worktree, or a container).
- **Structured output**: `--output-format stream-json` (requires `--agent-engine v2|v3` / `--v3`), "each line is a
  self-contained JSON object"; an interrupted run writes a final interruption record. **The event schema is not
  published** (Not found — searched: /docs/cli/headless/, /docs/reference/cli-commands/) [5].
- **Session resume**: `--resume`, `--resume-id <ID>`, `--list-sessions`; sessions persist under
  `~/.kiro/sessions/cli/`; resumed sessions keep their original agent [8][10].
- **Exit codes**: 0 success, 1 general failure (auth, args, operation), 3 MCP startup failure with
  `--require-mcp-startup` [9].
- **Streaming**: stdout streams in both modes; ACP mode (`kiro-cli acp`) streams `AgentMessageChunk`, `ToolCall`,
  `TurnEnd` over JSON-RPC 2.0 [10].
- **Limits**: credits are the only published cap; "Kiro pauses usage until you purchase more add-on credits or your
  plan resets" [11]. No RPM/concurrency numbers found (Not found — searched: /docs/billing/, /docs/billing/add-on-credits/,
  /docs/billing/subscription-management/ [404]).
- **Other**: `--effort low|medium|high|xhigh|max`, `/usage` prints a full credit breakdown in non-interactive runs [8][25].

**Kiro Crew** is the vendor's own "headless server" pattern: Python 3.12+, `kiro-cli` on the gateway host authenticated
via `kiro-cli login`, consumes your Kiro subscription credits when on the default `kiro-cli` backend (other ACP harnesses — Claude Code, Codex, KAS — are selectable since 0.6.0), crons in `crons.json`, Telegram channel built in [18][20].
This is the closest thing to our assistant server that any vendor in this survey ships.

**Devin CLI headless**: `devin -p "prompt"` / `--print` (non-interactive), `--permission-mode
normal|accept-edits|smart|dangerous|autonomous` (autonomous requires `--sandbox`, research preview), `--model`,
`-c/--continue`, `-r/--resume <id>`, `--export` (ATIF transcript), `devin doctor --json` (unverified as of 2026-09-24 — the fact-checker could not find `--json` on
`doctor` in [41]; `devin list --format json` and `devin models list --format json` are documented); non-interactive fails in
untrusted dirs unless `--respect-workspace-trust false` [41]. Auth: `devin auth login` (browser) or
`devin setup --force-manual-token-flow` for SSH [41]. No JSON event stream documented for `-p` (Not found — searched:
docs.devin.ai/cli/reference/commands.md). Quotas are "daily and weekly" on Pro, weekly-only on Max, amounts unpublished
[43]; sessions sleep after 30 min idle and do not meter while sleeping [44]. Native Windows cannot run the Devin sandbox — WSL 2 is
required [41].

**Amazon Q Developer**: the `q chat --no-interactive` path is now Kiro CLI [29]; the remaining Q surfaces (console,
Slack/Teams) are not scriptable [28].

---

## 4. Cost

**Kiro consumer/individual tiers** [1][2][11][12]:

| Tier | $/user/mo | Credits/mo | Models | Headless API key | Notes |
|---|---|---|---|---|---|
| Free | $0 | 50 | open-weight + Claude Sonnet 4.5 ("subject to limits"; Auto = "Sonnet-class quality or better" — exact set unverified as of 2026-09-24) | No | perpetual; data may be used for service improvement (opt-out); inputs may be stored up to 60 days for abuse detection [21] |
| Pro | $20 | 1,000 | all premium | Yes | first paid upgrade gets a $20 sign-up credit |
| Pro+ | $40 | 2,000 | all premium | Yes | |
| Pro Max | $100 | 5,000 | all premium | Yes | added 2026-06-11 |
| Power | $200 | 10,000 | all premium | Yes | |
| Enterprise | per-user Pro/Pro+/Pro Max/Power (1,000/2,000/5,000/10,000 credits) | as tier | + governance, SSO, no training on content; only tier eligible for Fable 5.1 | Yes | GovCloud ≈ +20%; overage is **opt-in** per tier; credits "consumed fractionally" (simple edits use fewer) [60]; "no Free tier" (unverified as of 2026-09-24 — the enterprise billing page lists only paid tiers but never says Free is excluded) |

- Add-on credits **$0.04/credit**, packs $5 (125 credits) to $100, ≤5 packs at a time, expire 12 months, consumed
  after plan credits [11]. Plan credits do not roll over [1].
- A credit is "a unit of work in response to user prompts", metered to 0.01, **per request not per token**; Auto = 1x,
  Sonnet 4.6/5 = 1.3x, Opus 5 = 2.2x, Fable 5.1 = 6x, GPT-5.6 Luna/Terra/Sol = 1.1/2.2/4.4x (doubling above 272K
  context), Qwen3 Coder Next = 0.05x [1][2][6]. Multipliers move: a 2026-07-31 blog post lowered GPT-5.6 Terra from 1.2x to
  1.0x and Luna from 0.6x to 0.1x (Sol unchanged at 2.4x) "passing on" an OpenAI price cut [61], yet the models page today
  prints Sol/Terra/Luna at 4.4x/2.2x/1.1x up to 272K (doubling above) [6] — the two vendor pages do not reconcile (whether
  the 1M-context launch on 09-14 re-based the scale is unverified as of 2026-09-24). Treat any multiplier as a snapshot.
- History: the August 2025 repricing (from $19/1,000 "interactions" to vibe/spec request buckets at $0.04/$0.20) drew
  "wallet-wrecking" coverage and a pricing bug that burned "four to six vibe requests" per request; AWS refunded
  August and later moved to the current single-credit model [47][48].

**Amazon Q Developer** [27]: Free — 50 agentic requests/mo, 1,000 lines of Java transformation; Pro — **$19/user/mo**,
agentic requests "included (with limits)" (number not printed), 4,000 transformation lines pooled, overage
$0.003/line; Pro benefits are retained when signing in to Kiro, but the mapping to a Kiro tier, credits or API keys is
(unverified as of 2026-09-24) [2].

**Devin Desktop / CLI (ex-Windsurf)** [36][37][43]: Free $0 (limited models, unlimited tab/inline), Pro **$20/mo**
(frontier models incl. Claude, "free SWE-2 access through October 10, 2026", cloud agents, on-demand credits for
overage), Max **$200/mo** ("significantly higher quotas", weekly-only cap), Teams $80/mo base + $40/seat, Enterprise
custom. Quota amounts are not published; on-demand credits roll over and never expire [43]. Fusion (lead + cheap
sidekick) is paid-plans-only [45]. ACU price: Not found — searched: docs.devin.ai/api-reference/overview.md,
admin/billing/usage.md, api-reference/teams-quickstart.md [404].

**API path (the only metered option in this family): Amazon Bedrock.** Anthropic's Bedrock guide says global endpoints carry
"no pricing premium" and regional endpoints a 10% premium [33]; that Bedrock global = Anthropic list price is (unverified as
of 2026-09-24 — aws.amazon.com/bedrock/pricing did not render current models, and Anthropic's pricing page says Bedrock has
independent regional pricing). List rates per 1M tokens are therefore Anthropic's first-party prices [32]:

| Model (Bedrock ID [33]) | Input | Output | Cache write 5m | Cache read | Batch in/out (Anthropic API) |
|---|---|---|---|---|---|
| Claude Fable 5.1 (`anthropic.claude-fable-5-1`) | $10 | $50 | $12.50 | $0.25 | $5 / $25 |
| Claude Fable 5 (`anthropic.claude-fable-5`) — **not offered on Kiro** | $10 | $50 | $12.50 | $0.25 | $5 / $25 |
| Claude Opus 5.5 (`anthropic.claude-opus-5-5`) — **not offered on Kiro**; Bedrock access gated ("See Access", not open to all) [33] | $4 | $20 | $5 | $0.20 | $2 / $10 |
| Claude Opus 5 (`anthropic.claude-opus-5`) | $5 | $25 | $6.25 | $0.50 | $2.50 / $12.50 |
| Claude Opus 4.8 (`anthropic.claude-opus-4-8`) | $5 | $25 | $6.25 | $0.50 | $2.50 / $12.50 |
| Claude Sonnet 5 (`anthropic.claude-sonnet-5`) | $2 | $10 | $2.50 | $0.20 | $1 / $5 |
| Claude Haiku 4.5 (`anthropic.claude-haiku-4-5`) | $1 | $5 | $1.25 | $0.10 | $0.50 / $2.50 |

Bedrock access is per-model: Fable 5.1, Fable 5, Opus 4.8, Opus 4.7, Sonnet 5 and Haiku 4.5 are open to all Bedrock customers;
Opus 5.5 and Opus 5 are "See Access" (criteria set in the console); Mythos models are invitation-only [33]. Neither Opus 5.5 nor
Fable 5 appears on Kiro's models page [6]. Bedrock is not Claude-only either: it now serves OpenAI GPT-5.6 Sol/Terra/Luna (and
GPT-6 Astra) through the Responses and Chat Completions APIs on `bedrock-runtime` (`global.openai.gpt-5.6-sol` etc.) and
`bedrock-mantle` (`/openai/v1`); GPT-5.6 Sol global pricing is $4/$20 per 1M (in-region +10%), doubling above 272K input [62].

A third AWS route exists: **Claude Platform on AWS** — Anthropic-operated (Anthropic is the data processor, Anthropic's data-use
terms apply), full first-party feature set (Agent Skills, code execution, betas), AWS provides SigV4/API-key auth, IAM and
billing via AWS Marketplace in Claude Consumption Units (CCUs), metered hourly and invoiced monthly in arrears; the `inference_geo`
parameter pins inference geography and `inference_geo=us` carries a **1.1x** price multiplier [63]. It is still metered, so it
falls under the same policy exclusion as Bedrock.

Bedrock caveats: the new `bedrock-mantle` Messages endpoint does **not** support Message Batches, structured outputs,
server-side web search/fetch, or the 2026 computer/browser toolsets [33]; batch pricing above is Anthropic-API pricing,
Bedrock batch availability for these models is (unverified). Claude 4.7+ models use a tokenizer that produces ~30% more
tokens for the same text [32]. Bedrock default quota: 2M input TPM [33]. Bedrock is metered billing, which the owner
has ruled out by policy; it is included only as the reference "API" column.

**Monthly cost estimate — 10 / 100 / 1000 jobs at ~150k input + 15k output tokens each.**

Assumptions (stated because Kiro does not publish a token→credit rate): (i) API column = Anthropic list price ×
tokens, no caching, no batch (Bedrock global ≈ list is unverified as of 2026-09-24 [32][33]); (ii) Kiro credits/job are **modeled, unverified as of 2026-09-24** (Kiro publishes no token→credit rate; the enterprise
billing page only says credits are "consumed fractionally" [60]): I
calibrated Auto so that $0.04 × credits ≈ Sonnet-class API cost of the job (Sonnet 5: $0.30 + $0.15 = $0.45 → ≈11
credits at 1.3x → ≈8.5 Auto credits; rounded to Auto 10, Sonnet 5 13, Opus 5 22, Fable 5.1 60 credits/job). The 2025
"4–6 requests per prompt" bug [47] shows real burn can exceed the model; treat the Kiro column as ±2x. (iii) Cheapest
tier that covers the credits, else Power + add-ons at $0.04.

| Jobs/mo | Kiro Auto (sub) | Kiro Sonnet 5 (sub) | Kiro Opus 5 (sub) | Kiro Fable 5.1 (Enterprise-only — not available on individual Pro/Pro+/Pro Max/Power seats; column is hypothetical) | API Sonnet 5 | API Opus 5 | API Fable 5.1 | API Haiku 4.5 |
|---|---|---|---|---|---|---|---|---|
| 10 | 100 cr → **$20** (Pro) | 130 cr → **$20** | 220 cr → **$20** | 600 cr → (Enterprise seat, price custom) | $4.50 | $11.25 | $22.50 | $2.25 |
| 100 | 1,000 cr → **$20** (Pro, at the edge) | 1,300 cr → **$40** (Pro+) | 2,200 cr → **$48** (Pro+ + 200 add-on) or $100 Pro Max | 6,000 cr → (Enterprise Power-tier seat + overage) | $45 | $112.50 | $225 | $22.50 |
| 1000 | 10,000 cr → **$200** (Power, at the edge) | 13,000 cr → **$320** (Power + 3,000 add-on) | 22,000 cr → **$680** (Power + 12,000 add-on) | 60,000 cr → (Enterprise; ≈$2,200 if priced at Power + $0.04 add-ons) | $450 | $1,125 | $2,250 | $225 |

Reading: at our scale (tens to low hundreds of jobs/month) a **$20–40 Kiro seat is 2–5x cheaper than list-price API**
for Sonnet/Opus-class work, and it is the only subscription in this survey with an officially sanctioned headless key.
At 1000 jobs/month the subscription advantage collapses to ~1.4x for Sonnet and ~1.65x for Opus and inverts for Fable
5.1 (6x multiplier — and Fable 5.1 is Enterprise-only, so the individual-seat column is hypothetical). Devin Desktop cannot be modeled (quotas unpublished).

---

## 5. Strengths & weaknesses per reviews

**Benchmarks.** Kiro publishes none for its harness; its models are third-party, so use the upstream numbers
(Anthropic/OpenAI docs) — Kiro's own model page only quotes vendor lines such as Opus 4.6 "top scores on Terminal-Bench
2.0 and SWE-bench Verified" [6]. Terminal-Bench 4.0 lists agent+model rows but the leaderboard table did not render in
this fetch, and no Kiro or Devin entry could be confirmed (Not found — searched: tbench.ai/leaderboard; unverified as of
2026-09-24) [56].
Artificial Analysis Intelligence Index: Opus 5.5 (max effort) 58, Fable 5.1 (max) 53; other models not visible in the
fetch [55] (unverified as of 2026-09-24). Cognition's SWE-2 self-reported: FrontierCode 1.1 Main 50.0%, DeepSWE 1.1 73.0%, Terminal-Bench 2.1
92.8%, Terminal-Bench 4 27.3%, "64% cheaper" than Fable 5.1; base Kimi K3 [39] — vendor numbers, unreplicated.
Cognition's Fusion harness claims "up to 39% more efficient" than competing harnesses [38]. A tech-insider.org
headline claims "88.6% SWE-bench" for Kiro [53] — low-credibility source, not used (unverified as of 2026-09-24).

**What Kiro is best at (attributed).**
- *Spec-driven workflow*: HN commenters called the workflow "neat" even while rejecting the price, and it spawned
  clones (a Claude skill for spec-driven development, 40 HN points, 2026-05) [48][54].
- *Governance features*: GeekWire (2026-05-12) on Requirements Analysis (LLM → SMT solver checks specs for
  contradictions), Parallel Task Execution ("~75%" faster on large projects, AWS claim), Quick Plan [52].
- *Model breadth on one seat*: Claude 4.x/5.x, GPT-5.6, DeepSeek, MiniMax, GLM, Qwen with published multipliers [6].
- *Enterprise adoption signals*: Netsmart (healthcare) and New Relic integrations, student program expanded by 121 universities across 16 countries (one free year, 1,000 credits/mo incl. premium models and Kiro Web) (2026-09-08) [58],
  ISO/IEC 27001:2022 coverage (2026-09-08), output indemnity for paid tiers [2][14][53].

**Weaknesses (attributed).**
- *Pricing opacity*: "Just give me dollar amounts, I feel like I'm paying these companies with vbucks" (HN, 2025-08);
  a developer estimated $550/mo light and $1,950/mo full-time under the 2025 scheme; The Register: "a wallet-wrecking
  tragedy" [47][48]. The single-credit model since then is simpler, but credits are still per-request with unpublished
  token rates [12], and multipliers are re-cut without a changelog of the scale (GPT-5.6 Terra/Luna lowered 07-31 [61], yet
  the models page prints higher figures today [6]).
- *Security record*: prompt-injection data exfiltration in the IDE (reported 2025-12-08, fixed 0.8.140 on 2026-01-26,
  $40 gift-card bounty; Mindgard published 2026-08-27) [51]; a "poisoned web page rewrites config → RCE" flaw reported
  by The Hacker News / CyberSecurityNews on 2026-07-21/22 [53].
- *Reliability controversy*: the FT reported (2026-02) that Kiro caused a 13-hour AWS Cost Explorer outage in one
  China region in December 2025 (the "13-hour", "China region" and "December" details are FT-paywalled and unverified as of
  2026-09-24; Amazon's own post says only "one of 39 geographic regions" and gives no duration [49]); Amazon says "user error — specifically misconfigured access controls — not AI",
  denies a second incident, and added mandatory peer review for production access [49][50]. Barrack AI's roundup
  cites four anonymous FT sources contradicting Amazon [50]. GeekWire frames the May features as a response to this
  scrutiny [52].
- *Region lock-in*: Kiro Web is us-east-1 only (universal vs Identity-Center-only: unverified as of 2026-09-24); Fable 5.1
  preview us-east-1 only; free/individual data stored in
  us-east-1 [13][15][21].
- *No API*: everything is CLI-shaped; the JSONL schema is undocumented [5].
- *Free-tier data use*: Free and social-login users' content "may be used for service improvement" unless opted out;
  Claude Fable 5.1 (Preview) traffic is retained up to 30 days and OpenAI GPT classifier-flagged traffic up to 30 days for offline abuse detection; Free-tier inputs may additionally be stored up to 60 days [21].

**Devin Desktop / Windsurf sentiment.** The Windsurf saga (OpenAI $3B deal collapsed, founders to Google, Cognition
acquisition, employee payout complaints) dominated HN in 2025 (1,055 / 672 / 502-point threads) [54]; 2026 coverage is
mostly Cognition press (Series E $2B+ at $48B, AWS strategic collaboration 2026-09-15, São Paulo expansion) [38]. No
2026 HN thread on the Devin Desktop rebrand surfaced (Not found — searched: hn.algolia "devin desktop"/"windsurf"
2026). Community reviews of Devin CLI headless use: Not found.

**Outage record.** Kiro has no reachable public status page (`status.kiro.dev` does not resolve); incidents are
tracked under AWS Health. Not found — searched: status.kiro.dev.

---

## 6. Finance / trading relevance

- **Real-time data**: none built in. Kiro has no web-search tool of its own (the Anthropic server-side web search is
  not available through Kiro or Bedrock [33]); browsing arrives only via MCP servers you configure [4].
- **Market-data connectors**: none first-party. Kiro Powers launch partners are Stripe, Postman, Supabase, Neon, Aurora,
  Datadog, Dynatrace, Figma, Netlify, Strands — payments/infra, not market data [23]. Any Alpaca/Tradier/Finnhub access
  would be our own MCP server (which Kiro CLI and Crew can load) [4][20].
- **Sentiment sources**: none.
- **Finance-specific products**: none in Kiro/Devin. AWS-side finance products (Amazon Quick, FinOps Agent) are unrelated
  to trading [31].
- **Restrictions**: AWS Service Terms §1.24 abuse detection applies to Kiro output [31]; Anthropic/OpenAI retention
  (OpenAI flagged traffic and all Fable 5.1 Preview traffic up to 30 days; Free-tier inputs up to 60 days) [21]. No trading-specific prohibitions found (Not found — searched: aws.amazon.com/service-terms
  for "Kiro").
- **Relevance for Atlas**: purely as a second Claude-family compute lane for *research/code* jobs (backtest tooling,
  thesis write-ups, adversarial review of ledgers) fed by our own MCP tools; not as a data or signal source. Kiro Web
  automations (cron → PR) are a plausible home for "weekly research PR" style loops if the repo is on GitHub [16].

---

## 7. Integration recipe for our server

**Recommended shape**: *Kiro Pro ($20) or Pro+ ($40) seat + `KIRO_API_KEY` + `kiro-cli chat --no-interactive
--output-format stream-json`*, wrapped as a second executor next to the Claude Agent SDK lane. Do **not** use
Bedrock (metered, against policy) and do not rely on the Free tier (no API keys, Sonnet 4.5 only (unverified as of 2026-09-24), content may be used
for training, inputs stored up to 60 days) [1][5][7][21]. Fable 5.1 is not purchasable on any individual seat; the strongest
individual-seat Claude is Opus 5 at 2.2x [6][59].

Setup on the Mac Mini (one-time):
```bash
curl -fsSL https://cli.kiro.dev/install | bash              # [4]
kiro-cli login --use-device-flow --license pro                # one-time device code; --license free|pro, --social google|github [7][8]
# mint an API key in the Kiro web console (paid tier), then:
launchctl setenv KIRO_API_KEY ksk_xxxxxxxx                    # or put it in the job's env file [7]
kiro-cli whoami --format json                                 # confirms which credential wins [8]
kiro-cli mcp add --name atlas --command "python -m atlas.mcp" # our own tools [8]
```

Per-job agent (checked into the project as `.kiro/agents/reviewer.json`, workspace beats `~/.kiro/agents`) [24]:
```json
{ "name": "reviewer", "model": "claude-sonnet-5",
  "prompt": "You are the adversarial reviewer. Never write outside the worktree.",
  "tools": ["read", "grep", "shell", "@atlas"], "excludedTools": ["write"],
  "resources": ["file://.context/CONTEXT.md"], "includeMcpJson": true }
```

Runner sketch (Python 3.12, sits next to the SDK executor):
```python
import json, os, subprocess
def run_kiro(prompt: str, cwd: str, agent="reviewer", effort="high", timeout=1800):
    cmd = ["kiro-cli", "chat", "--no-interactive", "--v3", "--agent", agent,
           "--effort", effort, "--trust-tools=read,grep,shell",
           "--require-mcp-startup", "--output-format", "stream-json", prompt]
    env = {**os.environ, "KIRO_API_KEY": os.environ["KIRO_API_KEY"]}
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    events = [json.loads(l) for l in p.stdout.splitlines() if l.startswith("{")]
    if p.returncode == 3: raise RuntimeError("MCP startup failed")          # [9]
    if p.returncode != 0: raise RuntimeError(p.stderr[-2000:])
    return events            # persist raw JSONL to the audit log; schema is undocumented [5]
```
Follow-ups: `kiro-cli chat --no-interactive --resume-id <ID> "continue"` [8]; run `kiro-cli chat --no-interactive
"/usage"` after each job and store the credit delta as the job's cost record [25].

Alternative for Telegram-native loops: run **Kiro Crew** (`curl -fsSL https://download.crew.kiro.dev/cli.sh | sh`,
Python 3.12+, `kirocrew setup && kirocrew gateway`, Telegram channel, `crons.json`) as a *parallel* assistant on the
same subscription credits [18][20]. It duplicates our scheduler/Telegram layer, so treat it as an evaluation target, not
a replacement — since Crew 0.6.0 (2026-09-05) the harness is selectable — `kiro-cli` is the default, and Claude Code, Codex or KAS can be chosen (Preview, Settings > Developer > Agent Backend), so Crew can also run on an existing Claude Code/Codex subscription instead of Kiro credits [13][20].

**Task-class fit** (this server):
- *Coding / build loops*: good — Sonnet 5 at 1.3x is the workhorse; Opus 5 at 2.2x for hard changes [6].
- *Code review / adversarial review*: good — a read-only custom agent with `excludedTools: ["write"]` and PreToolUse
  hooks (exit 2 blocks) gives a clean second-opinion lane on a different vendor's harness [22][24].
- *Research / long documents*: acceptable — 1M-context Opus 5 (Fable 5.1 only on Enterprise), but no built-in web search;
  bring MCP [6][33].
- *Chat (Telegram)*: only via Crew; otherwise our bot calls the runner.
- *Classification / routing*: poor value — per-request credits punish many tiny calls; keep on Haiku via the SDK lane.
- *Trading research*: same as research; no data tools; useful as a second-vendor "red team" on Atlas theses.

**Gotchas**
1. Auth precedence puts an *active browser session* above `KIRO_API_KEY` [7]; on a box where someone also uses the
   CLI interactively, the headless job may silently bill the wrong identity. Run jobs as a dedicated user.
2. The headless doc says an API key is *required* while the auth doc lists the session first — whether a device-flow
   session alone supports `--no-interactive` is untested (open question).
3. `stream-json` needs the V2/V3 engine flag; the event schema is unpublished and versions weekly [5][13] — pin the CLI
   version in launchd and snapshot raw JSONL.
4. Credits pause the account hard when exhausted [11]; the model has no per-token cost feedback except `/usage`.
5. Kiro Web (universal vs Identity-Center-only: unverified as of 2026-09-24) and Fable 5.1 preview are us-east-1 only;
   individual data is stored in us-east-1 [13][15][21].
6. Prompt-injection history in the IDE [51][53]: never point a Kiro agent at untrusted repos with write tools.
7. "Auto does not restrict its internal routing to the models an administrator has approved" [6] — pin a model.
8. Windsurf/Devin Desktop is a weaker second lane: quotas unpublished, `-p` has no JSON stream, `--sandbox` is research
   preview [41][43].

---

## 8. Verdict

- Kiro is the one non-Anthropic seat in this survey that (a) carries current Claude models (Sonnet 5 1.3x, Opus 5
  2.2x, Fable 5.1 6x is Enterprise-only via model governance, not on individual seats), (b) ships an official headless API key for paid tiers, and (c) has no found ToS clause
  against automation — exactly the "second Claude-family lane outside Anthropic consumer terms" the focus note asks for.
- At our volume (≤100 jobs/mo) a $20–40 seat is roughly 2–5x cheaper than list API for Sonnet/Opus work; the edge
  shrinks toward 1.4x at 1,000 jobs and inverts for Fable 5.1 (which is Enterprise-only anyway).
- Weak spots: undocumented JSONL schema, weekly CLI churn, per-request credit opacity, a 2026 security/incident record,
  and no built-in web search or finance data.
- Devin Desktop (ex-Windsurf) is a distant second: same $20/$200 price points, unpublished quotas, first-party SWE-2,
  but no structured headless output and no visible automation terms.
- Amazon Q Developer is end-of-life as a distinct product (IDE plugins EoS 2027-04-30); treat it only as a $19 legacy
  sign-in that keeps existing Q Developer Pro benefits inside Kiro; no vendor page maps Q Developer Pro to a Kiro paid tier, credits, or API keys, so do not buy it expecting headless access [2].

| Dimension | Score /10 | Why |
|---|---|---|
| Research | 5 | 1M-context Opus 5 / GPT-5.6 on a flat seat (Fable 5.1 Enterprise-only), but no search tool, no data connectors |
| Coding / agentic | 8 | Claude Opus 5/Sonnet 5 + GPT-5.6 on individual seats (Fable 5.1 Enterprise-only), spec/hook/agent harness, headless + resume + ACP |
| Cost efficiency | 7 | $20–40 covers our volume; credits opaque and multipliers re-cut; collapses at scale |
| Automation friendliness | 7 | Official API keys, exit codes, JSONL, MCP gating, Crew; minus undocumented schema and CLI churn |
| Trading research | 4 | Only as a second-vendor reviewer via our own MCP tools |

---

## 9. Sources

All accessed 2026-09-24.

1. https://kiro.dev/pricing/
2. https://kiro.dev/faq/
3. https://kiro.dev/docs/
4. https://kiro.dev/docs/cli/
5. https://kiro.dev/docs/cli/headless/
6. https://kiro.dev/docs/models/available-models/
7. https://kiro.dev/docs/getting-started/authentication/
8. https://kiro.dev/docs/reference/cli-commands/
9. https://kiro.dev/docs/reference/exit-codes/
10. https://kiro.dev/docs/cli/acp/
11. https://kiro.dev/docs/billing/add-on-credits/
12. https://kiro.dev/docs/billing/
13. https://kiro.dev/changelog/
14. https://kiro.dev/blog/
15. https://kiro.dev/docs/web/
16. https://kiro.dev/docs/web/automations/
17. https://kiro.dev/docs/crew/
18. https://kiro.dev/docs/crew/installation/
19. https://kiro.dev/blog/introducing-kiro-crew/
20. https://github.com/kirodotdev/kirocrew
21. https://kiro.dev/docs/privacy-and-security/data-protection/
22. https://kiro.dev/docs/hooks/
23. https://kiro.dev/docs/powers/
24. https://kiro.dev/docs/custom-agents/
25. https://kiro.dev/docs/reference/slash-commands/
26. https://kiro.dev/blog/cli-2-0/
27. https://aws.amazon.com/q/developer/pricing/
28. https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/what-is.html
29. https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/command-line.html
30. https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/q-developer-ide-end-of-support.html
31. https://aws.amazon.com/service-terms/
32. https://platform.claude.com/docs/en/about-claude/pricing
33. https://platform.claude.com/docs/en/build-with-claude/claude-in-amazon-bedrock
34. https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-5.md
35. https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html
36. https://devin.ai/desktop
37. https://devin.ai/pricing
38. https://cognition.com/blog
39. https://cognition.com/blog/swe-2
40. https://cognition.com/blog/introducing-devin-desktop
41. https://docs.devin.ai/cli/reference/commands.md
42. https://docs.devin.ai/cli/index.md
43. https://docs.devin.ai/admin/billing/self-serve.md
44. https://docs.devin.ai/admin/billing/usage.md
45. https://docs.devin.ai/cli/fusion.md
46. https://docs.devin.ai/api-reference/overview.md
47. https://www.theregister.com/2025/08/18/aws_updated_kiro_pricing/
48. https://news.ycombinator.com/item?id=44942600
49. https://www.aboutamazon.com/news/aws/aws-service-outage-ai-bot-kiro
50. https://blog.barrack.ai/amazon-ai-agents-deleting-production/
51. https://mindgard.ai/blog/amazon-kiro-data-exfiltration
52. https://www.geekwire.com/2026/aws-targets-ai-slop-with-new-spec-check-in-kiro-coding-tool-amid-scrutiny-of-agent-reliability/
53. https://news.google.com/rss/search?q=AWS+Kiro+2026&hl=en-US&gl=US&ceid=US:en (Google News index: The Hacker News 2026-07-21, CyberSecurityNews 2026-07-22, CRN 2026-02-20, Engadget 2026-02-21, SiliconANGLE/InfoWorld 2026-08-04, StartupHub 2026-09-08, Business Wire 2026-05-28, ChannelLife 2026-06-18)
54. https://hn.algolia.com/api/v1/search?query=kiro%20aws&tags=story (and the same API for "windsurf")
55. https://artificialanalysis.ai/models
56. https://www.tbench.ai/leaderboard
57. https://docs.devin.ai/llms.txt
58. https://kiro.dev/blog/students-2026/
59. https://kiro.dev/blog/fable-5-1/
60. https://kiro.dev/docs/enterprise/billing/
61. https://kiro.dev/blog/gpt-5-6-pricing/
62. https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-openai-gpt-56-sol.md (and model-cards.html)
63. https://platform.claude.com/docs/en/build-with-claude/claude-platform-on-aws

---

## Verification log (2026-09-24)

**Corrections applied: 12** — critical 1 (Fable 5.1 cost-table column is Enterprise-only/hypothetical), major 3 (verdict
Fable 5.1 tier wording; Kiro Crew harness selectable since 0.6.0; Q Developer Pro → Kiro is benefit retention, not a tier/API
route), minor 8 (Crew credit wording in §3; Free-tier retention text in §5 and §6; Sonnet multiplier printing; Devin lineup incl.
SpaceXAI `grok` and SWE-1.7; SWE-1.7 07-08 in cadence; student program 121 universities/16 countries; iOS TestFlight/no Android).

**Missing topics added (10)**: Kiro Web GA 2026-09-01 + Configuration Sync (§1, §2) [13]; Crew 0.6.0 selectable harness,
Remote Crews, Docker image, Node.js 22+, Python 3.12 (§2, §3, §7) [13][20]; Opus 5.5 / Fable 5 exist on Bedrock but not on
Kiro, Bedrock per-model access gating (§4) [6][33]; Claude Platform on AWS as a distinct Anthropic-operated, Marketplace/CCU-billed
route with `inference_geo=us` at 1.1x (§4) [63]; GPT-5.6 multiplier history 07-31 vs. current models page (§4, §5) [6][61];
`kiro-cli login` flags (§3, §7) [8]; Enterprise opt-in overage + fractional credit consumption (§4) [60]; Free-tier 60-day input
storage (§4, §5, §6) [21]; Devin `acp`, `migrate hooks`, WSL 2-only sandbox (§2, §3) [41]; Bedrock GPT-5.6 Sol/Terra/Luna via
Responses/Chat Completions on `bedrock-runtime` and `bedrock-mantle`, Sol $4/$20 global (§4) [62].

**Claims re-verified today (direct fetches)**: Fable 5.1 Enterprise-only via model governance, 6x, us-east-1, 09-16
(kiro.dev/blog/fable-5-1/, kiro.dev/changelog/, models page); Kiro Web GA 09-01 and Configuration Sync (changelog); Crew 0.6.0
harness selection + Remote Crews (changelog) and Docker/Node 22+/Python 3.12 (github.com/kirodotdev/kirocrew); `kiro-cli login`
flags (cli-commands reference); Enterprise tiers, opt-in overage, fractional credits (kiro.dev/docs/enterprise/billing/);
retention: Fable 5.1 Preview all traffic ≤30 d, OpenAI flagged ≤30 d, Free inputs ≤60 d, individual data in us-east-1
(data-protection page); Q Developer Pro benefit retention with no tier mapping (kiro.dev/faq/); Sonnet 4.6 1.3x (FAQ);
GPT-5.6 4.4x/2.2x/1.1x ≤272K, doubling above, 1M ctx (models page) and the 07-31 blog's 2.4x / 1.2→1.0x / 0.6→0.1x
(kiro.dev/blog/gpt-5-6-pricing/); students 121 universities/16 countries/1,000 credits/mo/one year (kiro.dev/blog/students-2026/);
Bedrock model list incl. Opus 5.5, Fable 5, GPT-5.6 Sol/Terra/Luna, GPT-6 Astra (model-cards.html); Bedrock Claude access table
and "global: no pricing premium / regional +10%" (platform.claude.com Bedrock guide); Claude Platform on AWS operator, CCU
Marketplace billing, `inference_geo` US 1.1x (platform.claude.com); Devin `acp`, `migrate hooks`, WSL 2 note, `--format json`
on `list`/`models list` (docs.devin.ai commands reference). Kiro Web docs page: "us-east-1 only" sentence sits inside the AWS
Identity Center paragraph; tier list Pro/Pro+/Pro Max/Power confirmed.

**Stale / unverified flags left in place (marked "(unverified as of 2026-09-24)")**: Kiro Web us-east-1 universal vs.
Identity-Center-only (§2, §5, gotcha 5); Bedrock global = Anthropic list price (§4); FT outage details 13-hour / China region /
December 2025 (§5); Q Developer Pro → Kiro tier/credits/API-key mapping (§1, §4, §8); `devin doctor --json` (§3 — note: a
re-fetch of [41] today reported the flag present, contradicting the fact-checker; left flagged pending a human read of the
page); Enterprise "no Free tier" (§4); Free-tier model set "Sonnet 4.5 only" (§1, §4, §7); Artificial Analysis / Terminal-Bench
/ tech-insider 88.6% (§5); cost-table credit calibration Auto 10 / Sonnet 13 / Opus 22 credits per job (§4, author's model);
GPT-5.6 multiplier reconciliation between the 07-31 blog and today's models page (§4). Still "Not found": stream-json event
schema, Kiro RPM/concurrency limits, Devin ACU price and quota amounts, Kiro status page. Web search was unavailable in this
session (budget exhausted); all re-verification used direct page fetches.

**Fact-checker overall quality rating: acceptable.** The verdict (§8) and integration recipe (§7) were re-read after the edits:
the recommended shape (Pro/Pro+ seat + `KIRO_API_KEY` + `stream-json`) is unchanged; the strongest individual-seat Claude is
now stated as Opus 5 (2.2x), Fable 5.1 being Enterprise-only; prices in §4 ($20/$40/$100/$200 seats, $0.04 add-on credits,
Opus 5 $5/$25 API) match §7/§8.
