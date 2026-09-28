# Mistral AI — research (as of 2026-09-24)

Research method: vendor docs/pricing/legal pages first, then Artificial Analysis, Hacker News, trade press and third-party pricing trackers. All prices in USD unless noted. Anything not confirmed on a primary page is marked "(unverified)". Citations are `[n]` into section 9.

## 1. Snapshot

**Company.** Mistral AI, Paris, founded April 2023 (Mensch / Lample / Lacroix); 1,000+ staff. Series D of €3B at a €21B valuation closed September 2026, led by Samsung with Scaleup Europe and PSG Equity — Mistral calls it the largest European tech equity round ever [20][49]. Earlier: ASML €1.3B for ~11% (Sept 2025) (unverified as of 2026-09-24 — a Wikipedia summary reads €1.5B within a €2B round at a €12B valuation; sources disagree), Microsoft multi-year infrastructure deal (July 2026), NVIDIA (March 2026), $830M bank debt for a Paris-area data centre (March 2026), plus a 10 MW Les Ulis inference site opening Q3 2026 [20][51]. Positioning: the "sovereign European" frontier lab — open weights (Apache 2.0 for most models), EU-hosted by default, and heavily enterprise/industrial (Airbus, BMW, ASML) [51].

**Consumer/agent product.** Le Chat was renamed **Mistral Vibe** on 2026-05-28 and merged with the coding agent into one product with *Work mode* and *Code mode*; "Chat mode" is being sunset [10][21].

**Current model lineup (docs.mistral.ai/models, 2026-09-24) [1][3][15][16][17][18][14]:**

| Family | Model | API ID | Context | Modalities | License | Released |
|---|---|---|---|---|---|---|
| Frontier | Mistral Medium 3.5 (128B dense) | `mistral-medium-2604` style (unverified as of 2026-09-24 — the model card exposes only the slug `mistral-medium-3-5-26-04` / `mistral-medium-3-5` and alias `mistral-medium-latest`; no dated id string could be confirmed) | 256k | text + image in | Modified MIT (open weights; revenue-cap exception) | card version date 2026-04-28 (v26.04); public preview announced ~2026-05-01; Mistral's launch post is dated 2026-05-22, the same day Devstral 2 was deprecated |
| Flagship open | Mistral Large 3 (675B MoE, 41B active) | `mistral-large-2512` | 256k | text + image | Apache 2.0 | 2025-12-02 |
| Mid | Mistral Small 4 (119B MoE, 6.5B active; 128 experts/4 active) | `mistral-small-2603` | 256k | text + image | Apache 2.0 | 2026-03-16 |
| Edge | Ministral 3 — 3B / 8B / 14B (instruct + reasoning variants) | `ministral-3b-2512` / `ministral-8b-2512` / `ministral-14b-2512` | 256k | text + image | Apache 2.0 | 2025-12-02 |
| Third-party hosted | Z.ai GLM 5.2 / GLM 5.3 | GLM ids (unverified) | 1M | text | open | Aug 2026 (GLM 5.2 first) [37] |
| Code | Codestral 25.08 (FIM/completion) | `codestral-2508` (alias `codestral-latest`) | 128k | text | proprietary (Premier) | 2025-07-30 |
| Code agent (legacy) | Devstral 2 (123B dense) / Devstral Small 2 (24B) | `devstral-2512` / `devstral-small-2512` (unverified) | 256k | text | Modified MIT / Apache 2.0 | 2025-12-09; deprecated on the API 2026-05-22 and superseded by Medium 3.5 (no longer on the pricing page) [11][13] |
| Reasoning (legacy) | Magistral Medium 1.2 / Magistral Small 1.2 | — | 128k | text | proprietary / Apache 2.0 | 2025; retired from Le Chat, capabilities folded into Small 4 / Medium 3.5 [11][18] |
| Audio | Voxtral Mini Transcribe 2 (`voxtral-mini-2602`), Voxtral Mini Transcribe Realtime (`voxtral-mini-realtime-2602`), Voxtral Small (`voxtral-small-2507`), Voxtral TTS (`voxtral-tts-2603`, CC BY-NC 4.0 (unverified as of 2026-09-24)) | as listed | — | audio in / audio out | mixed | Feb–Mar 2026 |
| Documents | OCR 4.1 (`mistral-ocr-4-1`, alias `mistral-ocr-latest`), OCR 4.0 | as listed | — | image/PDF | proprietary | GA 2026-08-31 [38] |
| Safety | Shieldstral 1.0 (3B, Apache 2.0), Mistral Moderation 2 (128k) | — | — | text + image | — | Aug 2026 [37] |
| Embeddings | Mistral Embed, Codestral Embed | `mistral-embed`, `codestral-embed` | — | text | proprietary | 2023 / 2025 |
| Math | Leanstral 1.5 (`labs-leanstral-1-5`, Lean 4 proving) | as listed | long | text | Apache 2.0 | 2026-06-30, retires 2026-09-30 [38] |

**Deprecation / retirement calendar (docs.mistral.ai/models deprecation table, 2026-09-24) [1][38].** Mistral publishes a deprecation date and a later retirement date per model; a routing plan should pin dated ids and track both:

| Model | API id | Deprecated | Retires | Replacement |
|---|---|---|---|---|
| Leanstral 1.5 | `labs-leanstral-1-5` | — | 2026-09-30 | none announced |
| Devstral 2 | `devstral-2512` | 2026-05-22 | 2026-07-31 | Mistral Medium 3.5 |
| Magistral Medium 1.2 | `magistral-medium-2509` | 2026-05-22 | 2026-07-31 | Mistral Medium 3.5 |
| Magistral Small 1.2 | `magistral-small-2509` | 2026-04-30 | 2026-07-31 | Mistral Small 4 |
| Mistral Medium 3.1 | `mistral-medium-2508` | 2026-05-22 | 2026-08-31 | Mistral Medium 3.5 |
| Mistral Small 3.2 | `mistral-small-2506` | 2026-04-30 | 2026-07-31 | Mistral Small 4 |
| Leanstral 26.03 | — | 2026-05-22 | 2026-06-30 | Leanstral 1.5 |
| Voxtral Mini Transcribe (25.07) | — | 2026-02-27 | 2026-05-31 | Voxtral Mini Transcribe 2 |
| Codestral 25.01 | `codestral-2501` | 2025-11-06 | 2025-11-30 | Codestral 25.08 |

No deprecation date is currently listed for Medium 3.5, Large 3, Small 4, Ministral 3, Codestral 25.08, Voxtral 2 or OCR 4.1. The `-latest` aliases (`mistral-medium-latest`, `mistral-small-latest`, `mistral-large-latest`, `codestral-latest`, `mistral-ocr-latest`) are repointed by Mistral when a new version ships (e.g. `mistral-ocr-latest` moved to OCR 4.1 on 2026-07-16 [38]); the docs do not publish a notice period for alias moves, so production code should use dated ids and treat alias changes as silent behaviour changes.

**Third-party hosting of the open weights.** Because Large 3, Small 4 and Ministral 3 are Apache 2.0 (Medium 3.5 Modified MIT), the same models are served outside Mistral's own API — useful as a fallback given Mistral's outage record (section 5): Microsoft Foundry sells `mistral-medium-3-5` (Preview, 128k in/out, tool calling listed as "No"), `mistral-ocr-4-0` (Preview), `Mistral-Large-3` (Preview), `mistral-document-ai-2512` and `Ministral-3B` directly [60]; OpenRouter's live models API (`/api/v1/models`, pulled 2026-09-24) returns 458 models of which 24 are Mistral-family ids (`mistralai/mistral-medium-3-5` $1.50/$7.50, `mistralai/mistral-small-2603` $0.15/$0.60, `mistralai/ministral-14b-2512` $0.20/$0.20, `mistralai/codestral-2508`, `mistralai/mistral-large-2512:batch` $0.25/$0.75, plus older Small 3.x/Medium 3.x/Nemo/Saba/Mixtral and `:batch` variants) — **none carries a `:free` suffix**. The API listed exactly 20 `:free` ids that day (Gemma 4, GLM 5.2, Qwen3.8-27B, Nemotron 3.x, Cohere North Mini Code, Poolside Laguna, etc.; aggregators quoting "22 `:free` variants" are a few days stale) and no Mistral model is among them, so under the owner's OpenRouter-free-tiers-only policy **OpenRouter is not a zero-cost Mistral lane** — it is a paid mirror at Mistral list price (Small 4 identical, Medium 3.5 identical) useful only as an outage fallback [61][64]; Amazon Bedrock and Google Vertex carry Mistral models but the current 2026 roster on each could not be read (unverified as of 2026-09-24). Third-party hosts run their own privacy terms — the EU-hosting / ZDR arguments in section 6 apply only to Mistral's own endpoints.

**Knowledge cutoffs:** Not published for Medium 3.5, Large 3 or Small 4 — the model cards and HF pages omit them [16][17][18]. Not found — searched: "Mistral Medium 3.5 knowledge cutoff", "Mistral Small 4 training data cutoff", "Mistral Large 3 cutoff".

**Release cadence.** Roughly one major model every 6–10 weeks through 2025–26 (Large 3 Dec, Devstral 2 Dec, Vibe 2.0 Jan, Voxtral Feb/Mar, Small 4 Mar, Medium 3.5 Apr, Vibe rebrand May, OCR 4 Jun, Leanstral Jun, Shieldstral Aug 4, Regional Endpoints GA + Priority Tier preview + European Compute Units Aug 11, Agentic Search Aug 20, HUMAIN partnership Aug 24) [20][37][38]. **Nothing model-related shipped in September 2026** up to the 24th: the month's items are the Series D (Sept 8), a Fortran-modernisation case study (Sept 9), the Cloudera sovereign-data partnership (Sept 10), the Mozilla/Firefox deal (Sept 16) and `mistral-common` 1.12.0 (Sept 22, tokenizer/validation library) [37][59][62]. Naming convention is `<family>-<YYMM>`.

**One-paragraph positioning.** Mistral is a second-tier-by-capability, first-tier-by-openness lab: its models sit below Anthropic/OpenAI/Google frontier on aggregate intelligence but are open-weight, EU-hosted, fast, and (for Large 3 / Small 4) very cheap. Since April 2026 the strategy shifted toward a single "Medium 3.5" dense model priced 5–10x above its own Large 3, which the developer community has criticised as strategically confused [25][26]. Its unique assets for this server are: an Apache-2.0 model family that runs locally on a 16 GB Mac (Ministral 14B), an open-source coding CLI (Vibe) with a real headless/JSON mode, and a subscription that bundles API credits.

## 2. Interfaces & surfaces

- **Consumer app (Vibe, ex-Le Chat):** web (chat.mistral.ai), iOS, Android [21][52]. No official macOS/Windows desktop app; only community WebKit wrappers exist on GitHub (unverified; not cited) [52]. Work mode: deep research, document generation, data analysis with spreadsheet uploads, meeting briefs, "schedule recurring workflows and tasks" on daily/weekly/monthly cadence with completion notifications, memory (since Sept 2025), Projects (July 2025), image generation/editing (Flux), voice input via Voxtral [10][21][52].
- **Browser/OS integrations:** Mozilla's Firefox Smart Window (beta AI browsing assistant) is powered by Mistral models as of 2026-09-16 — live in France and North America, UK/Germany expected later in 2026, zero data retention by default (conversations are not saved on Mozilla's servers; Mistral commits to ZDR). Mozilla's post does not name the specific model versions. No Mistral-branded browser extension and no macOS/Windows desktop app found [59].
- **Voice:** voice input in Vibe (Voxtral); Voxtral Realtime transcription and Voxtral TTS on the API ($0.003/min Voxtral Mini Transcribe 2, $0.004/min Voxtral Small, $0.006/min Voxtral Mini Transcribe Realtime, $0.016/1k chars TTS) [3][52].
- **CLI / agentic coding:** **Mistral Vibe CLI** (`mistral-vibe`, Apache 2.0, Python; install `curl -LsSf https://mistral.ai/vibe/install.sh | bash`, `uv tool install mistral-vibe` (recommended) or `pip install mistral-vibe`; requires **Python 3.12+**) [7]. Built-in tools per the README: `read`, `write_file`, `edit`, `bash` (plus managed `bash_sessions`/`bash_output`/`bash_stdin`), `grep`, `task` (subagents), `ask_user_question`, `todo` [7]. Vibe 2.0 (2026-01-27) added custom subagents, slash-command skills, unified agent modes, auto-updates [12]. Remote agents (cloud sandboxes, "teleport" a local session to the cloud, parallel sessions, auto-open PRs, GitHub/GitLab/Jira/Linear/Sentry/Slack hooks) shipped 2026-04/05 on Pro/Team/Enterprise [11][54]. Default model in Vibe is Medium 3.5 [11].
- **IDE plugins:** Vibe VS Code extension, JetBrains and Zed via Agent Client Protocol (ACP) [52]. The older **Mistral Code Enterprise** JetBrains/VS Code plugin is deprecated in favour of Vibe and works until March 2027 (unverified as of 2026-09-24 — marketplace page not readable by fetch) [53].
- **API + SDKs:** Official Python (`pip install mistralai`) and TypeScript SDKs; others are community [42]. Base URL `https://api.mistral.ai/v1`; the chat-completions surface is OpenAI-wire-compatible so the `openai` client works with a swapped `base_url` and key (third-party guides; Mistral itself says "we strongly recommend the official SDKs") [42]. No Anthropic-compatible endpoint found.
- **Code completion (FIM):** Codestral 25.08 (`codestral-2508`, 128k context, $0.30/$0.90) is served on a dedicated `/v1/fim/completions` endpoint (prompt + suffix) for fill-in-the-middle and low-latency completion, separate from chat completions — relevant only if the server ever runs completion-style code tasks rather than agentic ones [63][3].
- **Structured outputs:** `response_format={"type":"json_schema", "json_schema":{..., "strict": true}}` and Pydantic `BaseModel` support in the SDK [see SDK docs 42 and structured-output docs referenced there].
- **Tool use / function calling:** native, on all current text models [15][16][18].
- **Agents API / Conversations:** stateful conversations, handoffs, built-in connectors (web search, code execution in a sandbox, image generation, document library RAG, premium news), MCP servers as first-class tools (stdio, SSE/HTTP), registered "Connectors" that expose MCP servers to any agent without local transport [40][41]. Custom MCP servers in Vibe Work are allowed on Free/Pro too (account owner = admin); custom servers lack dynamic tool discovery, resources and prompt templates [41].
- **Batch API:** 50% off, all models, up to 1M in-flight requests per workspace; ZDR does *not* apply to batch [43][33].
- **Computer-use / browser agent:** none found for consumers or API. Not found — searched: "Mistral computer use", "Vibe browser agent".
- **Scheduled/automated tasks:** yes, Vibe Work mode (daily/weekly/monthly) [10]; Code-mode remote jobs can be triggered from Slack — the 2026-05-28 post says "coming in June"; shipment unverified as of 2026-09-24 [10]. No public REST API for scheduling Vibe tasks found.
- **Memory / projects / libraries:** Vibe memory + Projects; "Libraries" (document collections) in Studio and Vibe now use Agentic Search [21][39].
- **Messaging integrations:** Slack (Vibe remote-agent triggers, connectors) [10]. No official Telegram, WhatsApp or Discord channels; Teams appears only as a remote-agent trigger/notification hook alongside Slack (per launch coverage), not as a chat channel [28][54]. Not found — searched: "Mistral Vibe Telegram", "Le Chat WhatsApp".
- **Regional endpoints / Priority Tier:** Regional Endpoints GA (choose EU or US inference) and **Priority Tier** (public preview) shipped 2026-08-11. Priority Tier is "a committed service level for mission-critical workloads, including custom rate limits, backed by an uptime SLA" — the vendor's own mitigation for the outage record in section 5. **Terms (resolved 2026-09-24 from the docs page `docs.mistral.ai/inference/priority-tier`, found via the docs sitemap; the old `/deployment/ai-studio/priority-tier` path 404s) [73]:** billed as a **1.75× multiplier on Standard list price** ("a 75% premium on input, output, and cached tokens"; caching discounts apply before the multiplier), **99.5% uptime SLA** (Standard and Batch tiers carry none), "seconds" latency class via dedicated priority queues (no numeric TTFT commitment), and **custom per-model rate limits** (RPM/TPM "agreed with Mistral"). Enablement requires an organisation-level *Priority Tier entitlement* set up with a Mistral account executive — i.e. an enterprise agreement, not a self-serve PAYG toggle — after which requests opt in with `service_tier: "auto"` on chat completions (omitting it = Standard only); when Priority limits or capacity are exhausted the request falls back to Standard rather than failing, and the response reports `service_tier: "standard"`. Availability is model- and region-specific (global or regional endpoints). The docs no longer label it "preview". For this server: Medium 3.5 at Priority = $2.63/$13.13 per 1M, Small 4 = $0.26/$1.05 — but the entitlement gate makes it irrelevant to a single-owner account; the practical outage mitigation remains third-party hosts of the open weights (section 1) [37][35][73].

## 3. Headless / server automation fit

- **Non-interactive CLI:** `vibe --prompt "..." --max-turns N --output json|streaming|text` runs the `auto-approve` agent and exits; `--enabled-tools` (glob/regex allowlist), `--agent plan|accept-edits|auto-approve`, `--trust` for a folder, `--max-price` (documented as "indicative only, not reliable"), `--max-tokens`; `--continue`/`--resume SESSION_ID` need `log_interactions = true` [7][8]. **JSON output schema (from source, `vibe/cli/programmatic.py` + `vibe/app_server/models.py`, main branch 2026-09-24) [7][65][66]:** `--output json` prints, at session end, a JSON array of `PublicHistoryEntry` objects (`entry.model_dump(mode="json", by_alias=True)`); when teleport is used it is wrapped as `{"history": [...], "teleportUrl": ...}`. `--output streaming` writes the same objects one per line (NDJSON) on each `HistoryEntryAdded`/`HistoryEntryUpdated` app-server event. `PublicHistoryEntry` is a discriminated union on `type` ∈ {`message`, `reasoning`, `effect` (tool calls/results), `callback`, `checkpoint`, `notice`}; common fields `id`, `session_id`, `turn_id`, `created_at`, `updated_at` (ints), `generation_status` ∈ {`IN_PROGRESS`, `COMPLETED`}, `related_entry_id`; a `message` entry adds `role` ∈ {`system`,`user`,`assistant`}, `content: list[ContentBlock]`, `source`, `user_display_content`. Token usage/cost is **not** in the JSON output (the internal `TokenUsageUpdatedEvent`/`AgentStats` with `prompt_tokens`/`completion_tokens`/`cached_tokens` is exposed only in the TUI `/status` command) — parse the last `assistant` message entry for the result and meter tokens server-side from the Admin panel. The schema is unversioned and the CLI ships ~2 releases/week (v2.24.4 on 08-26 → v2.25.8 on 09-23: nine releases in four weeks) [67], so pin the version and add a schema smoke test. `--max-tokens N` ("interrupt if token usage exceeds budget") and `--max-price` are both in the README [7]. **Tool names (resolved from source 2026-09-24):** the registered string is **`read_file`, not the README's `read`**. `BaseTool.get_name()` derives every tool's name from its class name via `re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()`, `ToolManager` keys `_all_tools[name] = tool_class` on that value and matches `enabled_tools`/`disabled_tools` against it, and the read tool is `class ReadFile(BaseTool[...])` in `builtins/read_file.py` → `read_file` (likewise `WriteFile` → `write_file`, which is why the README's other names match) [74][75][76][68]. The README's `read` is stale; `--enabled-tools read` would enable nothing (exact match) — use `read_file` or a glob such as `read*`. The other registered builtins by the same rule: `edit`, `bash` (OS variants `powershell`, `git_bash`), `grep`, `todo`, `ask_user_question`, `task`, `skill`, `web_fetch`, `web_search`, `exit_plan_mode`, plus managed `bash_output`/`bash_stdin`-style helpers; the `--enabled-tools` matcher accepts exact names, globs like `bash*`, or `re:` regex, and `--disabled-tools` filters afterwards [7][68][76]. Because the name is derived from the class name, a class rename in one of the ~2 weekly releases silently changes the string — keep the schema smoke test asserting the tool list.
- **Auth modes:** (1) browser sign-in on first run (`vibe --setup`), which *provisions an API key tied to your Mistral account* and stores it in `~/.vibe/.env`; (2) `MISTRAL_API_KEY` env var; (3) `~/.vibe/.env`. No OAuth device-code flow for headless boxes is documented — do the browser login once on a machine with a display, then copy the key [9][58]. The CLI also accepts custom OpenAI-compatible providers via `config.toml` presets (e.g. a local Ollama) [7][9].
- **Subscription vs API — how it actually works (resolved 2026-09-24):** the Vibe CLI docs say explicitly that "Vibe Code doesn't have a separate coding allowance" — "Mistral plans include monthly usage that is shared across Studio, the API, and Vibe Code", and the CLI consumes that included monthly usage before triggering pay-as-you-go [9]. The pricing card's "all-day coding in the CLI, IDE, or on web" is therefore marketing for the *same* pool as the "$15/mo in API credits", both "subject to fair usage limits" whose numbers are unpublished [2][9]. Consequence for the router: Pro buys roughly $15 of metered inference per month (≈ 44 Medium 3.5 coding jobs of 165k tokens, or ≈ 475 Small 4 jobs), not an unmetered coding seat — so Mistral Pro is **not** the cheapest policy-clean subscription coding lane; it is a $15 prepaid credit with PAYG off as the spend cap. A separate, larger coding pool would have to be evidenced by a Mistral page stating one, and none does. The pricing page lists "$10/mo in API credits" on **Free** and "$15/mo in API credits" on **Pro** ($30 on Student) and "Test Mistral models in Studio" on Free [2]. When included usage runs out: if PAYG is enabled, you are billed at API rates; if not, Vibe Code stops until the next cycle. Partner-sold Pro plans (Google, Apple, Free Mobile, Orange) cannot enable PAYG; PAYG is off by default [9].
- **Terms conflict to flag:** the ROW consumer ToS (effective 2026-08-05) and the EU consumer ToS (effective 2026-08-07) both say Studio and "access to any of our APIs" are "limited to business customers", and the commercial ToS (2026-08-05) defines Customer as "the organization, company, or other entity that you represent" without excluding sole proprietors [30][31][77]. Meanwhile the pricing page advertises API credits on consumer plans [2]. **Sole-proprietor status (re-read 2026-09-24, resolved as far as the texts allow):** neither consumer document nor the commercial terms uses the words "sole proprietor", "self-employed" or "natural person"; the split is by *purpose*, not entity form. Both consumer ToS route you to the commercial terms "if you are accessing the Mistral AI Products for business purposes, such as to integrate the Mistral AI Products with your own products or services that are distributed to third-party end users", and the commercial terms route "an individual consumer" back to the consumer terms [30][31][77]. Read together: an individual who enables PAYG/uses Studio is by construction a "business customer" under the commercial terms (there is no third document), and nothing in them requires incorporation — "other entity that you represent" is broad enough to cover a one-person business. What remains genuinely unresolved is whether Mistral would treat an individual running a *personal* single-tenant automation server (no third-party end users) as "business purposes"; the consumer terms only name third-party distribution as the example. Practical reading (unverified): using your own API key from your own account for your own single-tenant server is normal Studio use under the commercial terms; the consumer restrictions 3(f)/3(g) ("extract content other than as permitted", "integrate the Products with products you offer") target scraping the Vibe web UI and reselling, not calling the API. Do **not** automate the Vibe web/mobile app itself; the CLI and API are the sanctioned programmatic paths [30]. **Third-party serving (row for the ToS cross-cut matrix):** the consumer terms forbid "integrate or combine the Mistral AI Products with any products you may offer or make available to third-parties … nor grant any third party access" and account sharing/resale, so anything a second person consumes (pickem league dashboard, shared project sites) cannot be produced under the Vibe subscription's consumer terms; the commercial terms expressly contemplate a "Customer Offering" ("Customer's own products and services that it makes available to third parties which involve use of the Mistral AI Products") and grant output ownership (§3.1) — but define Customer as "the organization, company, or other entity that you represent" and route individuals to the consumer terms [30][31]. Practical rule: **owner-only automation → either path; anything served to others → commercial/Studio API key, ideally on a business account**, and the usage policy's no-financial-advice clause still applies to any third-party-facing output (it does *not* apply to self-hosted open weights, which the policy carves out) [32].
- **Rate limits:** three ceilings (RPS, tokens/min, tokens/month), values shown only in Admin → Limits, never published. Free mode ≈ 1 RPS and ≈ 1B tokens/month per third-party trackers only (unverified as of 2026-09-24 — Mistral's help article publishes no numeric values). Tiers advance on cumulative *billed* spend: Tier 1 = enable PAYG, Tier 2 > $20, Tier 3 > $100, Tier 4 > $500, > $2,000 by support ticket; prepaying credits does not raise tier [4][5][6].
- **Sandboxing:** Vibe CLI has permission profiles and tool allowlists but no OS sandbox; remote agents run in Mistral-hosted isolated sandboxes [8][11]. Agents-API code execution runs Python in Mistral's sandbox [40].
- **Streaming:** SSE streaming on chat completions and Conversations; `--output streaming` in the CLI [8][42].
- **Session resume:** CLI `--continue` / `--resume`; Conversations API is stateful server-side [8][40].
- **Rate-limit gotcha for cron jobs:** Free mode's ~1 RPS means parallel agent jobs will 429; serialise or enable PAYG.
- **Progress-visibility plumbing (for the cross-doc table):** *quota/usage introspection* — **none programmatic.** Remaining included usage and the three rate-limit ceilings are visible only in the Admin panel (`admin.mistral.ai/plateforme/limits`); the public API reference documents no `/usage`, `/billing` or limits endpoint and no `x-ratelimit-*` response headers (a beta "Admin"/"Observability" group exists in the reference index but its contents could not be read — unverified as of 2026-09-24); the CLI offers only TUI `/status` (agent stats: tokens, steps, tool calls) and `/whoami` (signed-in user, workspace, plan), plus `/data-retention` [4][70][71]. *Telemetry export* — the CLI's `enable_telemetry` (default true) sends anonymous crash/feature telemetry to Mistral via a Sentry integration (`vibe/observability/sentry.py`, `logging.py`); there is **no OpenTelemetry exporter** and no local metrics hook, so per-job token/cost accounting must come from the API response `usage` object on direct SDK calls or from `TokenUsageUpdatedEvent` if the runner drives the app-server protocol instead of the CLI [68][72]. Net: per-call usage is observable (SDK), plan-level budget remaining is human-only.

## 4. Cost

**Consumer plans (Vibe) [2][46][47][48]:**

| Plan | Price | Includes | Caps |
|---|---|---|---|
| Free | $0 | web + mobile, limited messages/web searches, limited coding sessions, image gen, Studio access, **$10/mo API credits**, 100+ connectors | ≈ 25 msgs/day (third-party estimate, unverified); training on by default, opt-out available [34] |
| Pro | $14.99/mo ($5.99 student) | "more messages and web searches", "all-day coding in the CLI, IDE or web", more images, **$15/mo API credits** ($30 student), 15 GB storage, remote agents, Work mode, chat/email support | "fair usage limits" — unpublished; ≈ 150 msgs/day / 6× Free per trackers (unverified); PAYG overflow at API rates if enabled |
| Team | $24.99/user/mo ($50 minimum; $19.99 annual per one tracker, unverified) | Pro features + 30 GB/user, admin controls, domain verification, data export, org-wide training opt-out | as Pro |
| Enterprise | custom (≈ $20k+/mo entry per reviewer [28]) | custom models/agents/workflows, audit logs, SAML SSO, white-label, on-prem/VPC | negotiated |

**API list prices, $/1M tokens (mistral.ai/pricing/api, 2026-09-24) [3]:**

| Model | Input | Output | Notes |
|---|---|---|---|
| Mistral Medium 3.5 | 1.50 | 7.50 | cached input −90%; batch −50% |
| Mistral Large 3 | 0.50 | 1.50 | |
| Mistral Small 4 | 0.15 | 0.60 | |
| GLM 5.3 / 5.2 (Mistral-hosted) | 1.40 | 4.40 | |
| Ministral 3 14B / 8B / 3B | 0.20 / 0.15 / 0.10 | same as input | |
| Codestral 25.08 | 0.30 | 0.90 | FIM |
| Devstral 2 / Devstral Small 2 | 0.40 / 0.10 | 2.00 / 0.30 | from launch post [13]; deprecated 2026-05-22, retired 2026-07-31, no longer on the pricing page |
| Magistral Medium / Small 1.2 | 2.00 / 0.50 | 5.00 / 1.50 | third-party tracker [46], legacy |
| Voxtral Small (text) | 0.10 | 0.40 | |
| Mistral Embed / Codestral Embed | 0.10 / 0.15 | — | |
| OCR 4.1 | $4 / 1,000 pages | | Document AI $5 / 1,000 |
| Voxtral Mini Transcribe 2 / Small / Mini Transcribe Realtime | $0.003 / $0.004 / $0.006 per minute | | |
| Voxtral TTS | $0.016 / 1k characters | | |
| Tools (per 1k calls) | web search $30, code execution $30, premium news $50, image gen $100, Libraries $0.01/call + indexing $1/1M tokens + Libraries OCR $3/1k pages; Data Capture $0.04/1M tokens | | |
| Classifier fine-tune | $1 / 1M training tokens (min $4) + $2/model/month | | |

Cached-input and batch-discounted prices are stated as "up to 90%" and "half price" respectively; per-model cached rates are not itemised [2][3]. A HN commenter quoted Large 3 at $0.27/$0.81 — that is a third-party host price, not Mistral's [26].

**Free API tier ("Free mode" / Experiment):** all models available, phone verification, no card; ≈ 1 RPS and ≈ 1B tokens/month (third-party only, unverified as of 2026-09-24 — Mistral hides exact numbers) [4][5][6]. Evaluation-only per Mistral.

**Monthly cost estimate — 165k tokens/job (150k in + 15k out), no cache hits, no batch:**

| Jobs/mo | Medium 3.5 API | Large 3 API | Small 4 API | Subscription path (Pro $14.99 incl. $15 credits) |
|---|---|---|---|---|
| 10 | $3.38 | $0.98 | $0.32 | $0 on Free ($10 credits cover any of the three); Pro $14.99 |
| 100 | $33.75 | $9.75 | $3.15 | Medium: $14.99 + $18.75 overflow = $33.74; Large 3 or Small 4: $14.99 flat (credits cover) — or Free plan covers Large 3 ($9.75 < $10) |
| 1,000 | $337.50 | $97.50 | $31.50 | Medium: $337.49; Large 3: $97.49; Small 4: $31.49 (Pro credits only offset $15) |

Per-job: Medium 3.5 $0.3375, Large 3 $0.0975, Small 4 $0.0315, Ministral 14B $0.033. Batch mode halves the API column (Medium 3.5 → $169/1k jobs) if latency is tolerable. With prompt caching on a shared 100k system/context prefix the Medium 3.5 figure drops to roughly $0.20/job (unverified — depends on hit rate). 1,000 jobs = 165M tokens/month, under the reported ~1B free-mode cap but blocked by ~1 RPS. Assumptions: list prices from [3]; credits from [2]; "all-day coding" on Pro is modelled as the *same* $15 pool — the CLI docs state there is no separate coding allowance and that Vibe Code draws on the plan's shared included usage [9] (resolved 2026-09-24; see section 3). Fair-use limits inside that pool remain unpublished, so treat $15 as the ceiling, not the floor.

## 5. Strengths & weaknesses per reviews

**Benchmarks.**
- Artificial Analysis Intelligence Index: Medium 3.5 = 14 (rank 6/65 in its open-weight medium cohort), 149 tok/s, 2.3 s TTFT, $1.16/1M blended, "particularly expensive vs other open-weight models" [22]. Large 3 = 9 (rank 27/44, "below average", median 12), 77 tok/s, 1.1 s TTFT, $0.29 blended, rank #2 on cost per task, "very verbose" (9.8M output tokens vs 3.8M median) [23]. Small 4 (reasoning) = 11 (rank 12/65), 170 tok/s, 0.77 s TTFT, $0.10 blended (unverified as of 2026-09-24 — the AA page exposes $0.15/$0.60 list prices, "$0.02 per Intelligence Index task" and rank #1/65 on cost per task; the blended figure was not seen), "highly concise" [24].
- SWE-bench Verified: Medium 3.5 77.6% (Mistral's number; ahead of Devstral 2 72.2% and, per Mistral, Qwen3.5-397B-A17B), Devstral Small 2 68.0% [11][13][17]. τ³-Telecom 91.4 [17]. GPQA Diamond: Small 4 71.2 [18]; Large 3 ≈ 44 and AIME25 ≈ 40 per independent runs (unverified) [see 14 discussion]. Ministral 3 14B reasoning: 85% AIME25 (Mistral claim) [14].
- LMArena text: Large 3 debuted "#2 in OSS non-reasoning" (Mistral) [14]; a Sept 2026 tracker places Large 3 in a ~1300-Elo "capable" tier while Opus 4.8 / Gemini 3.1 Pro / GPT-5.5 sit ≥ 1500 (unverified third-party) [56]. Medium 3.5 does not appear in that table.
- Terminal-Bench / HLE: no Mistral-published numbers found. Not found — searched: "Medium 3.5 Terminal-Bench", "Mistral Humanity's Last Exam score".
- Agentic Search (Aug 2026): FinanceBench 26.7% → 86% correctness with Medium 3.5, OfficeQA Pro 6.3% → 51.9% (Mistral's own eval) [39].

**Professional reviews.**
- vibecodinghub (July 2026): Vibe CLI praised for open-source inspectable harness, multi-surface (terminal/VS Code/web), provider flexibility (local, Mistral, OpenAI-compatible), permission profiles, MCP/skills; criticised for confusing product naming, three-way pricing (subscription + API + inference), config complexity; verdict: choose Claude Code "when model quality and integrated workflows matter" [27].
- 0xminds Devstral 2 vs Claude Code: "has not dethroned Claude"; ~7× cheaper than Sonnet 4.5; Mistral's own human eval had Devstral 2 preferred over DeepSeek V3.2 42.8% vs 28.6%, but Claude Sonnet 4.5 preferred overall [29][13].
- teamazing enterprise review (updated 2026-09-16; note its model comparison still benchmarks "Mistral Large" against "GPT-4-tier / Claude 3 Sonnet" — stale (unverified as of 2026-09-24), though its enterprise-pricing and SOC 2 notes are current): 40+ MCP connectors, EU jurisdiction / no CLOUD Act exposure, ISO 27001; weaknesses — $20k+/mo enterprise entry, no WhatsApp/Teams/SMS channels, SOC 2 Type II still pending, "trails GPT-5 and Claude Opus on reasoning-intensive tasks" [28].

**Community sentiment (HN).**
- Medium 3.5 launch thread: "mixed-to-negative". *antirez*: releasing large dense models "no longer a fit unless crushing capabilities … you don't compete in any credible space"; *reissbaker*: "a model only on par with open-source models a quarter the size is a flop"; *Aurornis*: "almost every open weight model launch this year has claimed it matches or exceeds Sonnet … haven't seen it in practice"; *parsimo2010*: 70 GB dense weights → ~3.65 tok/s on a Mac Studio; *seb_lz*: 5× the price of Large 3 with unclear benefit; several note Qwen 3.6 27B matches it at ~1/5 the size [25]. (The antirez, Aurornis and seb_lz attributions are unverified as of 2026-09-24: the comments retrieved for those users on re-check were about DeepSeek v4 Flash on an M3 Ultra, run speed, and Vibe being buggy respectively — the quotes above may come from other comments by the same users.)
- AI Now Summit thread: *djvdq* "far more expensive than previous Mistral models and much more than DeepSeek"; *KronisLV* (Pro subscriber) "worse than Anthropic's models … at 20 EUR/month not a bad deal" (the EUR price quote is unverified as of 2026-09-24), 200k-class context "a deal breaker" (confirmed); *bermudi* "DeepSeek is the frontier in cost per intelligence" [26].

**Best at:** cheap, fast, EU-hosted open-weight inference (Large 3 / Small 4 / Ministral); multilingual chat; OCR (OCR 4.1 GA); speech-to-text pricing; local deployability (Apache 2.0 down to 3B); an honest open-source coding CLI with headless mode; document-heavy retrieval (Agentic Search on SEC filings).
**Weak at:** frontier reasoning and long agentic coding runs vs Claude/GPT/Gemini; pricing coherence (Medium 3.5); context ceiling 256k; no computer-use; no chat channels beyond Slack (Teams is only a trigger hook).

**Reliability.** StatusGator counts 971+ tracked outage events since May 2025, ~15 incidents in the last 90 days (count unverified as of 2026-09-24) and full-day outages on Aug 8–9 (two 24 h events) and Aug 13–16 2026 (four consecutive 23 h+ events); 5 incidents on Sept 21–22 (Sept 21: 1 h maintenance window and a 2 h availability drop for mistral-ocr-4-1; Sept 22: 9 min maintenance plus skill-creation issues of 10 min and 5 min); a "degraded performance" flag was showing on 2026-09-24 [36]. Vibe/Le Chat had several 20–70 min critical failures in Oct 2025 [status.mistral.ai incidents via 36]. Treat as noticeably less stable than Anthropic/OpenAI. **Normalised window for the cross-doc reliability table (source: StatusGator mirror of status.mistral.ai, read 2026-09-24; status.mistral.ai itself returns 403 to fetchers):** Sept 1–24 2026 = 5 logged events (all Sept 21–22: 1 × 25 min maintenance, 1 × 2 h `mistral-ocr-4-1` availability drop, 1 × 9 min minor incident, 2 × skill-service outages of 10 and 5 min), status "Up" on 09-24; August 2026 = the six full-day events (Aug 8–9, Aug 13–16) noted above. No uptime percentage is published anywhere and the commercial ToS §7.4 disclaims any uninterrupted-service warranty; the only SLA-bearing product is the **Priority Tier** (announced 2026-08-11; docs now state a **99.5% uptime SLA at 1.75× list price**, enterprise entitlement required — section 2) [36][31][37][73]. **Interactive-surface latency (Telegram round trip):** AA measured TTFT 0.77 s (Small 4), 1.1 s (Large 3), 2.3 s (Medium 3.5) at 170 / 77 / 149 tok/s [22][23][24] — all three are comfortably inside a chat-surface budget (sub-3 s first token, a 300-token reply in ≤ 5 s), with Small 4 the best chat lane of the three and Medium 3.5 acceptable; rating for the Telegram surface: **good** (Small 4) / **acceptable** (Medium 3.5), subject to the outage record. **Tool churn (operational burden):** Vibe CLI released v2.24.4 (08-26), v2.24.5, v2.25.0–v2.25.8 (09-04 → 09-23) — nine releases in four weeks, roughly twice weekly, with a Rust CLI rewrite (`cli-rust/`) landing in parallel and no changelog line flagging breaking changes or the JSON output; the model side adds four dated-id retirements between May and Sept 2026 plus silent `-latest` alias moves (section 1). Burden rating: **medium-high** — comparable to Codex CLI's weekly cadence, lower than Antigravity's 10-in-13-days, and mitigated by pinning `uv tool install mistral-vibe==<ver>` and dated model ids [67][7][38].

**Controversies.** March 2024 study: Mixtral 8x7B reproduced copyrighted text in 22% of tested prompts (vs GPT-4 44%) [20]. Aug 2026 consumer-terms change pulling API/Studio out of consumer terms with little announcement [30]. CEO lobbying French National Assembly against foreign AI in defence (May 2026) [20] — political, not product.

## 6. Finance / trading relevance

- **Real-time data:** API "web search" connector ($30/1k calls) and "premium news" ($50/1k) inside the Agents API; Vibe Work has web search and 100+ connectors. Le Chat has an AFP archive licence (since Jan 2025) [40][21][3]. No market-data connector (no Polygon/Alpaca/Bloomberg terminal integration) found. Not found — searched: "Mistral Bloomberg market data connector", "Le Chat stock data".
- **Finance products:** March 2026 "services for finance" announced at Bloomberg Invest — a sovereign/in-house deployment suite for banks and hedge funds, sold enterprise-only [50]. Agentic Search's headline benchmark is FinanceBench on SEC filings (26.7% → 86%) — directly relevant to 10-K/10-Q reading for Atlas research loops [39].
- **Sentiment sources:** none built in beyond web/news search; Voxtral could transcribe earnings calls at $0.003/min [3].
- **Restrictions:** Usage Policy (eff. 2026-06-11) prohibits using Mistral products "to provide professional advice without proper qualification … investment advice, financial planning, or any form of financial guidance" [32]. Internal paper-trading research for the owner's own use is not client-facing advice, but any Atlas output surfaced to third parties would be. No clause bars automated trading per se.
- **Data privacy for strategies:** API paid tiers do not train by default only if you toggle "Anonymous improvement data" off; Vibe Free/Pro train by default until opted out; ZDR only on PAYG stateless endpoints and never on Vibe or batch [33][34]. Data EU-hosted by default [35].

**Data-handling matrix per lane and auth mode (for the cross-doc table; sources [30][31][33][34][35][69]):**

| Lane / auth | Training use | Retention window | Residency | ZDR eligible |
|---|---|---|---|---|
| Vibe web/mobile, Free or Pro (consumer login) | **On by default**; opt out in Admin → Manage Vibe → Privacy (separate toggle from API) | **Resolved (Privacy Policy §5, read 2026-09-24):** "we keep your Input and Output until you delete your account or until you delete the conversation from Vibe" — i.e. indefinite, user-controlled deletion, no automatic window [78]; account-level periods on top (identity data 5 y after contract end, sign-up data 1 y after deletion, connection logs 1 rolling year, invoices 10 y) [69] | EU by default | **No** (never for Vibe Work/Chat, any plan) |
| Vibe Team / Enterprise | Team: admin-controlled org-wide opt-out; Enterprise: **off by default** | as above; Enterprise can disable features that transfer data to subprocessors | EU (Regional Endpoints let Enterprise pick US) | No (Vibe) |
| Vibe CLI on the account-provisioned API key (Free credits / Pro credits, PAYG off) | Follows the **API/Studio** toggle ("Anonymous improvement data"), not the Vibe toggle — flip both | API rule applies: generation time + **30 rolling days** abuse monitoring [78]; ZDR unavailable in Free mode | EU default; explicit US endpoint available | **No** — ZDR requires PAYG enabled |
| Studio / API, PAYG on, stateless endpoints (`/v1/chat/completions`, `/v1/fim/completions`, `/v1/embeddings`, `/v1/ocr`, `/v1/audio/*`, classifiers/moderation) | Opt-out toggle; commercial ToS §4.2: no training unless opted in (except Labs/Preview models, which always train) | **Resolved:** Privacy Policy §5 — "Except for specific APIs, we keep your Input and Output for the period necessary to generate the Output and then for **thirty (30) rolling days to monitor abuse** (unless zero data retention is activated)" [78]; DPA adds that personal data becomes inaccessible **30 days after termination** of access [79]; **zero** with ZDR (granted on request, discretionary, shown in Admin → Privacy) [33] | EU default, US selectable | **Yes** (request via help centre) |
| Agents / Conversations / Libraries / Batch / Files / fine-tuning | Same toggle | Privacy Policy §5: Agents API input/output kept "until you terminate your account"; fine-tuning data "until you delete it from Mistral AI Studio or until you terminate your account" [78]; batch input/output files persist until deleted; no ZDR | EU default | **No** |
| Open weights self-hosted (Ollama Ministral 3, Small 4 via vLLM) | n/a — never leaves the box | n/a | local | n/a (usage policy explicitly does not apply) |

Routing implication for the paper-trading lab: proprietary theses may go to the PAYG stateless API **only after ZDR is granted**, or to local Ministral/Small 4; never to Vibe (any plan) or to the credit-funded CLI key while PAYG is off, because ZDR is unavailable there and the Labs/Preview training carve-out applies regardless of toggles.

## 7. Integration recipe for our server

**Recommended path.** Mistral Vibe **Pro ($14.99)** for one owner account, using the *API key the CLI provisions* for both (a) `vibe --prompt … --output json` coding/review jobs and (b) direct `mistralai` SDK calls for classification/routing/research, all drawing on the $15/mo credits with PAYG **off** so spend is capped at the subscription [2][9]. Start on **Free** ($10 credits, ~1 RPS) to measure; the Free→Pro decision is purely about the coding fair-use pool and RPS. Keep Ministral 3 14B in Ollama (9.1 GB, 256k ctx) as the zero-cost/offline classifier [44].

**Model routing.** `mistral-small-2603` (reasoning_effort none/high) for routing, summarisation, adversarial second opinions; `mistral-large-2512` for cheap bulk research drafts; Medium 3.5 only for coding/code review where SWE-bench-class performance matters and cost ($0.34/job) is acceptable; OCR 4.1 for statements/PDF ingestion; Agentic Search via Studio Libraries for filing analysis [3][15][16][18][39].

**Minimal sketches.**

```bash
# one-time, on a machine with a browser; copies key to ~/.vibe/.env
vibe --setup
# headless coding job from launchd/cron
vibe --prompt "Add retry logic to src/runner/http.py; run pytest" \
     --agent auto-approve --max-turns 25 --output json \
     --enabled-tools read_file --enabled-tools write_file --enabled-tools edit --enabled-tools bash \
     > /tmp/vibe.json   # flag is repeatable (one pattern per flag) [7]; names are class-name-derived — `read_file`, not the README's `read` [74][75]
# stdout = JSON array of PublicHistoryEntry; result = last entry with type=="message" && role=="assistant" [65][66]
```

```python
# pip install mistralai
import os, json
from mistralai import Mistral
c = Mistral(api_key=os.environ["MISTRAL_API_KEY"])  # same key Vibe provisioned
r = c.chat.complete(
    model="mistral-small-2603",
    messages=[{"role": "user", "content": "Classify this job request: ..."}],
    response_format={"type": "json_schema", "json_schema": {
        "name": "route", "strict": True,
        "schema": {"type": "object", "properties": {"lane": {"type": "string"}},
                   "required": ["lane"]}}},
)
print(json.loads(r.choices[0].message.content))
```

```python
# OpenAI-client drop-in (single dependency across providers)
from openai import OpenAI
o = OpenAI(base_url="https://api.mistral.ai/v1", api_key=os.environ["MISTRAL_API_KEY"])
```

```bash
# local fallback, no network
ollama pull ministral-3:14b        # 9.1 GB, 256k ctx, image input [44]
```

**Task-class fit.**
- Research: Large 3 / Small 4 for drafts and summarisation — cheap, fast; not for final reasoning-heavy synthesis.
- Coding: Vibe CLI + Medium 3.5 for bounded tasks and PR review; Claude remains primary for long agentic runs [27][29].
- Code review / adversarial review: good second-reviewer with a *different* model family (Medium 3.5 or Small 4 high-reasoning) — diversity is the value, not superiority.
- Chat / Telegram front-end: fine, but no native Telegram; route through the server.
- Classification / routing: Small 4 or local Ministral 14B — best value in the lineup [24].
- Trading research: filings/OCR/Agentic Search strong; no market data; keep outputs internal (usage policy) [32][39].

**Cross-doc dimension rows (Mistral lane, 2026-09-24).**
- *Concurrency on subscription auth:* no published parallel-session cap for the Vibe CLI; the binding limit is the account's RPS ceiling (Free ≈ 1 RPS third-party estimate, PAYG tiers unpublished, Priority Tier custom) [4][5][73]. Parallel `vibe --prompt` processes share one API key and one RPS bucket, so fan-out N > 1 on Free is effectively serial; remote agents on Pro advertise "parallel sessions" in Mistral's cloud, but no number is published [11][54]. Scheduler design: treat Mistral as concurrency 1 on Free, and size by tier RPS (Admin → Limits) on PAYG.
- *Credential lifecycle:* `vibe --setup` provisions a long-lived **API key** (not an OAuth token) and writes it in **plaintext** to `~/.vibe/.env` (`MISTRAL_API_KEY=`); no TTL, no refresh, no Keychain — it works headlessly until revoked in Admin → API keys, and revocation is the only expiry, so the failure mode on a headless box is a 401 with no warning. Mitigation: keep the key in the server's existing secret store and export `MISTRAL_API_KEY` at job start instead of relying on `~/.vibe/.env`; the SDK path uses the same key [9][58][7].
- *Prompt-injection / sandbox posture:* Vibe CLI has permission profiles and tool allow/deny lists but **no OS sandbox** (no Seatbelt equivalent); `web_fetch`/`web_search` and MCP tools are builtins, so fetched pages reach the model unfiltered; `auto-approve` mode runs `bash` without prompts. Rank: below Codex (Seatbelt) and Claude Code (hook-enforced guards), roughly level with opencode/Hermes-class CLIs. For untrusted Telegram/web input route through the SDK (no tools) or run Vibe in a throwaway workspace with `--disabled-tools "bash*" --disabled-tools "web_*"`; Shieldstral 1.0 / Moderation 2 exist as classifier gates but add a call per input [8][68][37]. Mistral-hosted remote agents and Agents-API code execution do run in Mistral's sandbox [11][40].
- *Host resource budget:* the Vibe CLI is a Python 3.12 process (≈ 150–300 MB RSS, unmeasured here — no official figure); Ollama with Ministral 3 14B Q4 needs ≈ 9.1 GB weights + KV cache, i.e. it cannot coexist with Postgres/Redis and a second model on 16 GB; Ministral 8B (6.0 GB) is the realistic always-on local size [44]. No daemon is required for the hosted lane.
- *Reviewer independence:* Mistral trains its own pretraining stack (Mixtral/Large/Medium lineages since 2023) and no distillation-from-Anthropic allegation is recorded against it, unlike the kimi/minimax/deepseek/qwen docs; it uses its own tokenizer (`mistral-common`) — so as a second-opinion lane its errors are plausibly less correlated with Claude's than the Chinese open-weight lanes', at the cost of lower absolute capability (AA 9–14) [20][62][22]. Mistral also hosts GLM 5.x, which inherits GLM's independence caveats — pick a Mistral-family id for adversarial review.
- *Empirical calibration:* the cost table assumes 165k tokens/job and 0% cache hits; Medium 3.5's −90% cached-input price means a 70% cache-hit share cuts its per-job cost from $0.34 to ≈ $0.19 and Small 4 from $0.032 to ≈ $0.018 — the subscription-vs-metered verdict does not flip for Mistral at any hit rate because the $15 Pro credit is the same pool either way (section 3). Real jobs/month and cache share from `volumes/audit_log` were not read for this pass (out of scope per task) — plug them into the per-job figures above.
- *Progress-visibility sink:* Mistral emits only the SDK `usage` object per call (`prompt_tokens`, `completion_tokens`, cached tokens) and nothing plan-level [70]; a common cross-lane event schema for this server should therefore carry `{lane, model_id, prompt_tokens, completion_tokens, cached_tokens, cost_usd_est, ts}` computed server-side from list price × `service_tier` multiplier, with remaining-budget inferred as `15 − Σcost` per month for Pro (reset on billing day) — no Mistral endpoint can confirm the inferred figure.

**Gotchas.**
1. Free-mode ~1 RPS: serialise Mistral jobs in the scheduler or they 429 [4][5].
2. `--max-price` is documented as unreliable; enforce budgets with `--max-turns`/`--max-tokens` and PAYG off [8].
3. Vibe writes `~/.vibe/.env` and `config.toml`; sessions only resumable when `log_interactions = true` [7][8].
4. Two separate training opt-outs (Vibe vs API) — flip both [34].
5. Consumer-terms wording restricts "API access to business customers" while the pricing page grants credits — keep to your own key/own server and avoid multi-account tricks (explicitly prohibited) [30][2].
6. Medium 3.5 and Devstral 2 are Modified-MIT (revenue-cap clause); Large 3/Small 4/Ministral are Apache 2.0 [16][13][15][18].
7. Devstral Small 2 (Ollama 15 GB) and Small 4 do not fit a 16 GB Mac; only Ministral 3 ≤ 14B (Q4) does, ~10–27 tok/s on M-series 16 GB [44][45][55].
8. Outage record is worse than the US labs; add fallbacks (third-party hosts of the open weights — section 1; Priority Tier's 99.5% SLA needs an enterprise entitlement, so it is not an option for a single-owner account) [36][73].
11. `--enabled-tools read` silently enables nothing: the registered name is `read_file` (class-name-derived); the README is stale [74][75].
9. Vibe CLI needs Python 3.12+ (`uv tool install mistral-vibe`); the `--output json` schema is only defined in source (`PublicHistoryEntry`, section 3), unversioned, with no usage/cost in the payload and ~2 releases a week — pin `mistral-vibe==<ver>` and add a schema smoke test before wiring it into the runner [7][65][66][67].
10. Pin dated model ids; `-latest` aliases move without a published notice period, and Leanstral 1.5 retires 2026-09-30 (section 1 calendar) [1][38].

## 8. Verdict

1. Mistral is the cheapest credible EU-hosted, open-weight option; its coding CLI is Apache 2.0 with a documented headless JSON mode (as are Google's Gemini CLI and OpenAI's Codex CLI) — what is unique is that the CLI's default models are themselves open-weight and can be self-hosted.
2. Its models are mid-pack on intelligence (AA index 9–14), competitive on speed and price for Large 3 / Small 4, and its flagship Medium 3.5 is priced like a frontier model without frontier reviews.
3. The subscription's "$15/mo API credits" and "all-day" Vibe coding are **one shared pool** (resolved 2026-09-24, section 3) — so Pro is a $15 prepaid credit with PAYG-off as a hard spend cap, which is policy-clean but small: it does not undercut Claude Max / ChatGPT Plus-class subscription coding seats on volume, only on price-per-month. OpenRouter carries no Mistral `:free` variant, so there is no zero-cost hosted Mistral lane; the zero-cost lane is local Ministral 3.
4. Reliability (full-day outages in Aug 2026) and the 2026 consumer-terms churn are the main operational risks — Priority Tier (99.5% SLA at 1.75× list, but enterprise-entitlement-only) is out of reach for a single owner, so third-party hosts of the open weights are the practical mitigation; the usage policy's "no financial advice" clause is manageable for internal research.
5. Use it as a cheap second-opinion / bulk-research / OCR / local-fallback lane, not as a Claude replacement.

Fit scores (1–10): research **6**, coding/agentic **6**, cost efficiency **8** (Large 3 / Small 4; 4 if Medium 3.5), automation friendliness **7**, trading research **5**.

**Calibrated row for the cross-provider scorecard** (anchors proposed for every doc so the router can compare: 10 = best lane in the landscape on that axis, 5 = usable with caveats, 1 = unusable; automation = headless CLI/SDK + auth on a display-less box + budget control + quota introspection; trading = data access + policy clearance + ZDR path for proprietary theses):

| Axis | Score | Anchor rationale |
|---|---|---|
| Research | 5 | AA index 9–14, no Terminal-Bench/HLE, strong OCR + Agentic Search on filings; below Claude/GPT/Gemini synthesis |
| Coding/agentic | 5 | SWE-bench 77.6% (self-reported), open CLI with resolved JSON schema, but reviews say "has not dethroned Claude"; ~2 CLI releases/week |
| Cost | 7 | Small 4 rank #1/65 cost-per-task; Pro pool is only $15; no OpenRouter `:free`; Medium 3.5 priced like frontier → 7 not 8 |
| Automation | 6 | headless mode + `--max-turns`/`--max-tokens` good; API key must be provisioned via browser once; **no programmatic quota introspection**, no OTEL; Free mode ~1 RPS |
| Trading | 4 | no market-data connector; usage policy bars financial guidance to third parties; ZDR only on PAYG stateless — workable for internal paper-trading only |
| Interactive (Telegram) latency | 8 | TTFT 0.8–2.3 s, 77–170 tok/s |
| Third-party serving | 4 | consumer terms forbid it; commercial terms allow it but assume an entity customer |
| Reliability | 4 | six full-day outages Aug 2026, 5 events Sept 21–22, no published uptime for Standard; Priority Tier 99.5% SLA at 1.75× exists but needs an enterprise entitlement |

## 9. Sources

Access date for all: 2026-09-24.

1. https://docs.mistral.ai/models — current model table, IDs, licenses.
2. https://mistral.ai/pricing/ — Vibe plan cards (Free/Pro/Team/Enterprise, API credits).
3. https://mistral.ai/pricing/api — per-model API, OCR, audio, tool, fine-tune prices.
4. https://help.mistral.ai/en/articles/698531-why-am-i-hitting-api-rate-limits-and-how-do-i-increase-them — rate-limit tiers.
5. https://pricepertoken.com/endpoints/mistral/free — free-mode ≈1 RPS / ≈1B tok/mo (third party, "verified June 2026").
6. https://benchlm.ai/free-tier/mistral — free-mode tier progression (2026-09-14).
7. https://github.com/mistralai/mistral-vibe — CLI install, flags, config, MCP, license.
8. https://docs.mistral.ai/vibe/code/cli/work-with-cli — programmatic mode, agents, resume.
9. https://docs.mistral.ai/vibe/code/cli/api-keys-profiles — auth, plan usage across Studio/API/Vibe, PAYG behaviour.
10. https://mistral.ai/news/vibe-agent/ — Vibe launch 2026-05-28, Work/Code modes, scheduled tasks, plans.
11. https://mistral.ai/news/vibe-remote-agents-mistral-medium-3-5/ — Medium 3.5 in Vibe, remote agents, pricing, license.
12. https://mistral.ai/news/mistral-vibe-2-0 — Vibe 2.0 (2026-01-27).
13. https://mistral.ai/news/devstral-2-vibe-cli/ — Devstral 2 / Small 2 specs, SWE-bench, prices.
14. https://mistral.ai/news/mistral-3/ — Large 3 & Ministral 3 launch (2025-12-02).
15. https://docs.mistral.ai/models/mistral-large-3-25-12 — Large 3 model card.
16. https://docs.mistral.ai/models/model-cards/mistral-medium-3-5-26-04 — Medium 3.5 model card.
17. https://huggingface.co/mistralai/Mistral-Medium-3.5-128B — weights, license, benchmarks.
18. https://huggingface.co/mistralai/Mistral-Small-4-119B-2603 — Small 4 specs, GPQA 71.2.
19. https://mistral.ai/news/mistral-small-4/ — Small 4 announcement (2026-03-16) (seen via search snippet only).
20. https://en.wikipedia.org/wiki/Mistral_AI — company, funding, release timeline, controversies.
21. https://en.wikipedia.org/wiki/Mistral_Vibe — Le Chat → Vibe history, features, platforms.
22. https://artificialanalysis.ai/models/mistral-medium-3-5 — AA index 14, speed, price.
23. https://artificialanalysis.ai/models/mistral-large-3 — AA index 9, verbosity.
24. https://artificialanalysis.ai/models/mistral-small-4 — AA index 11, concision.
25. https://news.ycombinator.com/item?id=47949642 — HN Medium 3.5 thread.
26. https://news.ycombinator.com/item?id=48327526 — HN AI Now Summit / pricing thread.
27. https://vibecodinghub.org/blog/mistral-vibe-review — Vibe review (July 2026).
28. https://www.teamazing.com/blog/mistral-le-chat-enterprise-review/ — enterprise review (upd. 2026-09-16).
29. https://0xminds.com/blog/guides/mistral-devstral-2-review-vibe-coding — Devstral 2 vs Claude Code.
30. https://legal.mistral.ai/terms/row-consumer-terms — consumer ToS eff. 2026-08-05.
31. https://legal.mistral.ai/terms/commercial-terms-of-service — commercial ToS eff. 2026-08-05.
32. https://legal.mistral.ai/terms/usage-policy — usage policy eff. 2026-06-11 (financial-advice clause).
33. https://help.mistral.ai/en/articles/347612-can-i-activate-zero-data-retention-zdr — ZDR scope.
34. https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training — training defaults/opt-out.
35. https://help.mistral.ai/en/articles/347629-where-do-you-store-my-data-or-my-organization-s-data — EU hosting default.
36. https://statusgator.com/services/mistral-ai — outage history.
37. https://releasebot.io/updates/mistral — Aug–Sep 2026 release notes (Agentic Search, Regional Endpoints, GLM 5.2, Shieldstral).
38. https://docs.mistral.ai/resources/changelogs — OCR 4.1, Leanstral 1.5 entries.
39. https://mistral.ai/news/agentic-search — Agentic Search (2026-08-20), FinanceBench.
40. https://mistral.ai/news/agents-api/ — Agents API built-in tools, MCP, handoffs.
41. https://docs.mistral.ai/vibe/work/connectors/mcp-connectors — custom MCP in Vibe Work.
42. https://docs.mistral.ai/resources/sdks — official Python/TypeScript SDKs.
43. https://mistral.ai/news/batch-api/ — batch 50%, 1M in-flight.
44. https://ollama.com/library/ministral-3 — 3b 3.0 GB / 8b 6.0 GB / 14b 9.1 GB, 256k.
45. https://ollama.com/library/devstral-small-2 — 24b 15 GB.
46. https://www.cloudzero.com/blog/mistral-api-pricing/ — third-party price roll-up (upd. 2026-09-04), legacy model prices.
47. https://www.grizzlypeaksoftware.com/articles/p/mistral-ai-pricing-in-2026-pro-costs-free-tier-limits-and-api-rates-lx4o2n2v — Free ≈25 / Pro ≈150 msgs/day (2026-04-01, unverified).
48. https://whichai.fyi/compare/mistral/ — Pro = 6× Free, PAYG beyond base (2026-08-14).
49. https://techcrunch.com/2026/09/08/mistral-raises-e3b-as-sovereign-ai-becomes-big-business/ — Series D.
50. https://www.bloomberg.com/news/articles/2026-03-03/mistral-ai-rolls-out-services-for-finance-to-protect-firm-data — finance offering (headline/snippet; paywalled).
51. https://mistral.ai/news/ai-now-summit-2026/ — Airbus/BMW/ASML, Les Ulis DC, Emmi acquisition.
52. https://mistral.ai/products/vibe/ — Vibe feature list, platforms, IDE/ACP.
53. https://plugins.jetbrains.com/plugin/27493-mistral-code-enterprise — Mistral Code deprecated, works to March 2027.
54. https://www.marktechpost.com/2026/05/02/mistral-ai-launches-remote-agents-in-vibe-and-mistral-medium-3-5-with-77-6-swe-bench-verified-score/ — remote agent details.
55. https://huggingface.co/unsloth/Devstral-Small-2-24B-Instruct-2512-GGUF — Q4_K_M ≈14.3 GB (search snippet).
56. https://www.swfte.com/lmarena — Sept 2026 arena tiers (third party, unverified).
57. https://docs.mistral.ai/deployment/ai-studio/tier — official tier page (404 on 2026-09-24; superseded by [4]).
58. https://docs.mistral.ai/getting-started/quickstarts/vibe-code/install-cli — browser sign-in, partner-plan PAYG restriction (search snippet).
59. https://mistral.ai/news/mistral-x-mozilla/ — Firefox Smart Window partnership (2026-09-16), regions, ZDR.
60. https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-models/concepts/models-sold-directly-by-azure — Foundry "Mistral models sold by Azure" table (updated 2026-09-23).
61. https://openrouter.ai/mistralai — 48 Mistral models on OpenRouter (free variants not visible in fetch).
62. https://mistral.ai/news — news index, Aug–Sep 2026 items (Series D, HUMAIN, Cloudera, Mozilla).
63. https://docs.mistral.ai/models/codestral-25-08 — Codestral 25.08 card: id, 128k, Premier, `/v1/fim/completions`.
64. https://openrouter.ai/api/v1/models — live models JSON pulled 2026-09-24: 458 models, 24 Mistral-family ids with prices, 20 `:free` ids, none Mistral.
65. https://github.com/mistralai/mistral-vibe/blob/main/vibe/cli/programmatic.py — `--output json` = `PublicHistoryEntry.model_dump(mode="json", by_alias=True)` array at finalize; streaming emits on `HistoryEntryAdded`/`HistoryEntryUpdated`; `{"history", "teleportUrl"}` wrapper.
66. https://github.com/mistralai/mistral-vibe/blob/main/vibe/app_server/models.py — `PublicHistoryEntry` union (`type`: message/reasoning/effect/callback/checkpoint/notice), field list, `PublicEntryGenerationStatus`, `PublicTurnStopReason`.
67. https://github.com/mistralai/mistral-vibe/releases — v2.24.4 (2026-08-26) … v2.25.8 (2026-09-23) release cadence.
68. https://github.com/mistralai/mistral-vibe/tree/main/vibe/core/tools/builtins — builtin tool modules (`read_file.py`, `write_file.py`, `edit.py`, `bash.py`, `grep.py`, `todo.py`, `ask_user_question.py`, `task.py`, `skill.py`, `web_fetch.py`, `web_search.py`, `exit_plan_mode.py`); `vibe/core/types.py` event classes (`TokenUsageUpdatedEvent`, `LLMUsage`).
69. https://help.mistral.ai/en/articles/347628-how-long-do-you-store-my-data — account-level retention periods (5 y / 1 y / 1 rolling year / 10 y); no per-conversation or API window.
70. https://docs.mistral.ai/api/ — API reference index: no usage/billing/limits endpoint, no rate-limit headers documented; beta Admin/Observability groups listed.
71. https://github.com/mistralai/mistral-vibe/blob/main/vibe/cli/commands.py — slash commands: `/status` (agent statistics), `/whoami` (user, workspace, plan), `/data-retention`; no `/usage` or `/cost`.
72. https://docs.mistral.ai/vibe/code/cli/configuration — `enable_telemetry` (default true, anonymous, no prompts/outputs); `enabled_tools`/`disabled_tools` pattern syntax; no OTEL.
73. https://docs.mistral.ai/inference/priority-tier — Priority Tier: 1.75× list-price multiplier (75% premium on input/output/cached), 99.5% uptime SLA (none for Standard/Batch), custom per-model RPM/TPM, `service_tier: "auto"` opt-in with fallback to Standard, entitlement via account executive (read 2026-09-24; path found via docs sitemap).
74. https://github.com/mistralai/mistral-vibe/blob/main/vibe/core/tools/base.py — `BaseTool.get_name()`: class name → snake_case (`re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()`).
75. https://github.com/mistralai/mistral-vibe/blob/main/vibe/core/tools/builtins/read_file.py — `class ReadFile(BaseTool[...])` → registered name `read_file`; `write_file.py` has `class WriteFile`.
76. https://github.com/mistralai/mistral-vibe/blob/main/vibe/core/tools/manager.py — `ToolManager` keys `_all_tools[tool_class.get_name()]`; `enabled_tools` allowlist then `disabled_tools` denylist via `name_matches`.
77. https://legal.mistral.ai/terms/eu-consumers-terms-of-service — EU consumer ToS eff. 2026-08-07: personal use "excluding Mistral AI Studio and access to any of our APIs, which are limited to business customers"; business-purpose users routed to commercial terms; no sole-proprietor language.
78. https://legal.mistral.ai/terms/privacy-policy — §5 retention: Vibe input/output until account or conversation deleted; API input/output "period necessary to generate the Output and then for thirty (30) rolling days to monitor abuse (unless zero data retention is activated)"; Agents API until account termination; fine-tuning data until deleted.
79. https://legal.mistral.ai/terms/data-processing-addendum — personal data inaccessible 30 days after termination of access; abuse monitoring waived only under ZDR; no per-request window.

## Verification log (2026-09-24)

**Corrections applied:** 13 total — 2 major (Firefox Smart Window browser surface; verdict's "only major lab" CLI claim), 11 minor (Codestral id/context/date/tier; Medium 3.5 release-date wording; Ministral ids; Devstral 2 deprecation; Voxtral per-minute prices ×2; Libraries/Data Capture tool pricing; two StatusGator incident descriptions; partner-plan PAYG wording; Teams as trigger hook).

**Claims re-verified (source):**
- Mozilla/Firefox Smart Window: 2026-09-16, France + North America live, UK/Germany later 2026, ZDR default — mistral.ai/news/mistral-x-mozilla/.
- Codestral 25.08: `codestral-2508`, 128k, Premier, released 2025-07-30, `/v1/fim/completions` — docs.mistral.ai/models/codestral-25-08.
- Ministral 3 14B: `ministral-14b-2512`, 256k, Apache 2.0, 2025-12-02 — docs.mistral.ai/models/ministral-3-14b-25-12.
- Medium 3.5: card version 2026-04-28 (v26.04), 256k, Modified MIT — docs.mistral.ai/models/model-cards/mistral-medium-3-5-26-04.
- Deprecation table (Devstral 2 / Magistral 1.2 / Medium 3.1 / Small 3.2 / Leanstral 26.03 / Voxtral Mini Transcribe 25.07 / Codestral 25.01 dates) — docs.mistral.ai/models and docs.mistral.ai/models/devstral-2-25-12.
- Leanstral 1.5 retirement 2026-09-30; OCR 4.1 GA 2026-08-31; `mistral-ocr-latest` repointed 2026-07-16 — docs.mistral.ai/resources/changelogs.
- Priority Tier public preview (custom rate limits, uptime SLA) + Regional Endpoints GA, 2026-08-11 — releasebot.io/updates/mistral (docs page 404).
- Vibe CLI Python 3.12+, `uv tool install mistral-vibe`, tool names, `--output json|streaming` semantics — github.com/mistralai/mistral-vibe.
- PAYG off by default; partner-sold plans cannot enable PAYG; usage shared across Studio/API/Vibe — docs.mistral.ai/vibe/code/cli/api-keys-profiles.
- Foundry carries `mistral-medium-3-5`, `mistral-ocr-4-0`, `Mistral-Large-3` (all Preview), `mistral-document-ai-2512`, `Ministral-3B` — learn.microsoft.com Foundry models page (updated 2026-09-23).
- September 2026 news: Series D (09-08), Fortran case study (09-09), Cloudera (09-10), Mozilla (09-16), mistral-common 1.12.0 (09-22); no model release — mistral.ai/news, releasebot.io.

**Stale / unconfirmable flags left in place (marked "unverified as of 2026-09-24"):** Medium 3.5 dated API id; ASML investment size; HN 47949642 antirez/Aurornis/seb_lz attributions; HN 48327526 KronisLV EUR price quote; AA Small 4 blended $0.10; Voxtral TTS CC BY-NC 4.0; Mistral Code Enterprise plugin works-until-March-2027; StatusGator ~15 incidents/90 days; free-mode ≈1 RPS / ≈1B tokens (third-party only); Slack-triggered jobs shipment; teamazing's stale model comparison; Bedrock/Vertex 2026 rosters. (Resolved in the gap-fill pass below: Pro coding pool = shared $15 credits; `--max-tokens`; JSON schema; OpenRouter `:free`.)

**Gap-fill pass (2026-09-24, WebFetch + live OpenRouter API only; search budget exhausted):**
- RESOLVED — Pro "all-day coding" pool = same shared included-usage pool as the $15 API credits (docs: "Vibe Code doesn't have a separate coding allowance") [9]; cost table, §3, §8 and scorecard updated. Mistral Pro is not the cheapest policy-clean subscription coding lane.
- RESOLVED — Vibe `--output json`/`streaming` schema read from source (`PublicHistoryEntry` union, no usage in output) [65][66]; `--max-tokens` confirmed in README [7]; builtin tool modules enumerated [68] — the exact registered string for the read tool (`read` per README vs `read_file.py` module) is the one residual to confirm with `vibe --help`.
- RESOLVED — OpenRouter: 24 Mistral ids, zero `:free`; 20 `:free` ids total that day, none Mistral [64].
- ADDED — ToS cross-cut row (third-party serving: consumer terms forbid, commercial terms allow for entity customers) [30][31]; data-handling matrix per lane/auth mode [33][34][35][69]; progress-visibility plumbing (no programmatic quota, no OTEL, Sentry-only telemetry) [4][70][71][72]; normalised reliability window (Sept 1–24: 5 events; Aug: 6 full-day) + Priority Tier SLA status [36][31]; Telegram-surface latency rating from AA TTFT [22][23][24]; tool-churn burden (9 CLI releases in 4 weeks) [67]; calibrated scorecard row with proposed cross-doc anchors.
- STILL OPEN — beta Admin/Observability API contents; Bedrock/Vertex 2026 roster; HUMAIN details; whether Mistral treats a personal no-third-party automation server as "business purposes" (texts silent).

**Gap-fill pass 2 (2026-09-24, WebFetch + curl only; WebSearch budget exhausted):**
- RESOLVED — Priority Tier: 1.75× list, 99.5% uptime SLA, custom per-model limits, `service_tier: "auto"` with Standard fallback, enterprise entitlement only (docs page relocated to `/inference/priority-tier`, found via sitemap) [73]; §2, §5, §7 gotcha 8, §8 and scorecard updated.
- RESOLVED — Retention without ZDR: API = generation + 30 rolling days abuse monitoring; Vibe = until conversation/account deleted; Agents API = until account termination; DPA 30-day post-termination inaccessibility [78][79]; §6 matrix updated.
- RESOLVED — Vibe read tool registered string is `read_file` (class-name-derived `get_name()`; README's `read` is stale) [74][75][76]; §3, §7 sketch and gotcha 11 updated.
- PARTIALLY RESOLVED — sole-proprietor status: EU + ROW consumer terms and commercial terms split by purpose (business vs personal), never by entity form; an individual on PAYG/Studio falls under the commercial terms by construction; the residual question is only whether a personal, no-third-party server counts as "business purposes" [30][31][77].
- ADDED — cross-doc dimension rows in §7 (concurrency, credential lifecycle, injection/sandbox posture, host resource budget, reviewer independence, calibration sensitivity, progress-visibility event schema).

**Fact-checker overall quality rating:** good.
