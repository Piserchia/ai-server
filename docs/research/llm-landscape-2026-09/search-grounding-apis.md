# Search/grounding APIs — Brave Search, Tavily, Exa, Parallel — research (as of 2026-09-24)

Scope note: these are retrieval vendors, not LLM vendors, so "model lineup" below means
search modes/endpoints (the thing you pick per call and pay for), and the per-job cost
model is expressed in searches + page fetches per job rather than tokens. Research method:
vendor docs/pricing/terms pages first, then status pages, HN threads and vendor blogs.
WebSearch was unavailable in this session (budget exhausted), so every source was fetched
directly; Reddit/X could not be fetched and are flagged where relevant. Fact-checked and
corrected 2026-09-24 — see the verification log at the end.

## 1. Snapshot

| Vendor | Company / status | "Model lineup" (modes you pay for) | Index / freshness | Release cadence |
|---|---|---|---|---|
| **Brave Search API** | Brave Software; independent web index, "over 30 billion pages", "100+ million daily page updates", SOC 2 Type II [1] | Plans: **Search** ($5/1k, 50 QPS) and **Answers** ($4/1k + $5/M tokens in+out, 2 QPS); endpoints `web/search`, `news/search`, images, videos, `suggest`, `spellcheck`, LLM Context, Answers, `local/pois`, `web/rich` (weather/stocks/sports) [1][2][3] | Own crawl; `freshness` filter `pd/pw/pm/py` or date range; `count` max 20 web / 50 news, `offset` max 9 [4][5] | Steady feature drops: Place Search (Feb 2026), SOC 2 (Oct 2025), AWS Marketplace (Jul 2025) — dates from HN submissions [12], not a Brave changelog; Brave's changelog pages 404 and only "2025-02-20 Rich Search API" is visible on the get-started page [3] (unverified as of 2026-09-24) |
| **Tavily** | Tavily AI; acquisition by Nebius for $275M announced Feb 2026 [27] | `search_depth` = `ultra-fast` / `fast` / `basic` (1 credit) / `advanced` (2 credits); `topic` = `general` / `news` / `finance`; `extract` basic/advanced; `map`; `crawl`; `research` model `mini` / `pro` / `auto` [15][17][19] | Aggregated/curated web + own extraction; `time_range` d/w/m/y, `start_date`/`end_date`, `include_domains` up to 300 [17][21] | Active: blog posts weekly in Sep 2026 (IBM CUGA, BMO AML case studies, 6-vendor comparison) [26] |
| **Exa** | Exa Labs (YC S21); Launch HN May 2025 [37]; $85M Series B Sep 2025 [38] | `type` = `instant` / `fast` / `auto` (default) / `deep-lite` / `deep` / `deep-reasoning`; `category` = company, publication, news, personal site, **financial report**, people; `contents` = text / highlights / summary (JSON-schema); `/answer`; `/contents`; Monitors; Websets; Agent runs (fixed effort minimal → xhigh at $0.012–$1.00/request, plus metered `auto` (default cap $5) and `ultra` (default cap $20, launched 2026-09-24) with `budget.maxCostDollars`) [80]; an OpenAI-compatible `/chat/completions` endpoint (`model: "exa"`, routes to `/answer`) [30][31][32][33][79] | Own neural (embedding) index + live crawl; `contents.maxAgeHours` (0 = always fresh, -1 = cache only); `numResults` up to 100; `includeDomains` up to 1,200 entries [31][32] | Fast. Changelog Jun–Sep 2026 [73]: Agent API (Jun 16), Exa Connect paid data sources via `dataSources` on agent runs (Jun 24), Agent inside the MCP (`agent_run`, Jul 1), `publication` category replacing `research paper` with `pdf`/`github`/`tweet` deprecated and `startCrawlDate`/`endCrawlDate` now ignored (Jul 23), Dynamic Highlights research preview (Aug 28), Agent `ultra` effort (Sep 24) [30][33][73] |
| **Parallel Web Systems** | Founded by Parag Agrawal (ex-Twitter CEO); "raised $130M" per its Feb 2026 HN hiring post [59] (self-reported; no press release checked — unverified as of 2026-09-24) | Search `mode` = `turbo` (~200 ms, $1/1k) / `fast` (~700 ms, $1/1k) / `basic` (~1 s, $5/1k) / `advanced` (~3 s, $5/1k, **default**); Extract $1/1k URLs; Task API processors `lite`→`ultra8x` ($5–$2,400/1k runs); Responses API (`model: "parallel"`, `reasoning.effort` low/med/high, $10–$250/1k); Monitor ($3–$10/1k); FindAll; Entity Search [41][42][43][49][50] | Own crawler "ShapBot/0.1.0" [53]; `source_policy` (include/exclude domains, `after_date`), `freshness` [44][51] | Very fast: Search/Extract went beta→GA, Monitor alpha→GA, FindAll v0→v1 all within the last year [58]. Note `fast` mode is only about a month old (GA 2026-08-21) [74]; Responses API gained domain-filter mapping (`filters.allowed_domains` → `source_policy.include_domains`) plus a `web_search_call` trail per search (2026-09-18) and OpenAI-style `mcp` tool support plus `data_sources`/Data Connectors at medium/high effort (2026-09-23) [74] |

Positioning in one paragraph each:

- **Brave** sells raw SERP-style results from a genuinely independent index at Google-CSE-replacement prices. It is the closest thing to "Google for agents" here, with the broadest general coverage, but it is a *results* API: you fetch pages yourself (the LLM Context endpoint exists but its docs 404'd for me; see §9). Its terms are the most restrictive on storing results and on AI-model training [7].
- **Tavily** is the LangChain-era default "search tool for agents": one credit-based API returns LLM-ready snippets, optional `answer`, optional `raw_content`, with `finance` and `news` topics, plus extract/map/crawl/research. 1,000 free credits/month with no card [15][22]. Now Nebius-owned [27].
- **Exa** is embedding-first ("search by meaning"), strongest for entity/company/people/paper discovery and structured extraction (JSON-schema summaries, Websets, Monitors), weaker for breaking news per multiple independent commenters [60][25]. $10 free credit resets monthly [30].
- **Parallel** is the newest and cheapest: $1/1k for `fast`/`turbo` modes, excerpts already LLM-optimized, $5 free credit/month plus an up-to-$80 signup bonus, a keyless MCP, a device-login CLI with `--json`, and a Task API for long-running deep research [41][42][46][47]. Its own docs refuse to publish head-to-head benchmarks and tell you to build a gold set [71].

## 2. Interfaces & surfaces

| Surface | Brave | Tavily | Exa | Parallel |
|---|---|---|---|---|
| Consumer app | Brave Search (web) + Brave browser; API is a separate product | Playground on website only | exa.ai web search + Websets UI | None (developer platform only) |
| Browser / OS integrations | Brave browser is the consumer surface; not relevant to server use | None | None | None |
| Voice | None | None | None | None (turbo mode is pitched for voice apps) [43] |
| CLI | `bx` CLI (`bx web`, `bx images`, `bx config set-key`) referenced in Brave's OpenClaw guide [8]; npm page 403'd and github.com/brave/bx unreachable, so package name/install source are unverified as of 2026-09-24 | None official | None official | `parallel-cli` via `pipx install "parallel-web-tools[cli]"`, brew, npm; `search`/`extract`/`research run` all take `--json`; exit codes 0/2/3/4/5 [47] |
| REST API | `https://api.search.brave.com/res/v1/...`, header `X-Subscription-Token` [3] | `POST https://api.tavily.com/search`, `Authorization: Bearer tvly-...` [17] | `POST https://api.exa.ai/search`, `Authorization: Bearer` or `x-api-key` [31] | `https://api.parallel.ai/v1/search`, header `x-api-key` [44] |
| Official SDKs | None found for Python (community packages exist; unverified) | `tavily-python` (sync + `AsyncTavilyClient`, `get_search_context`, `qna_search`), JS [23] | `exa-py` (`Exa`, `AsyncExa`, Python 3.9+), `exa-js` [35] | `parallel-web` (Stainless-generated, `Parallel`/`AsyncParallel`, Python 3.9+), TS `parallel-web` [54] |
| OpenAI/Anthropic-compatible endpoint | Answers plan is "OpenAI SDK compatible" [1] | No | `/chat/completions`: point the OpenAI SDK at `https://api.exa.ai` with `model="exa"`; it routes to `/answer` (so `/answer`'s $5/1k applies), returns citations, `extra_body={"text": true}` adds full source text [33][79] | Responses API is OpenAI-Responses-shaped: `model: "parallel"`, `reasoning.effort`, `previous_response_id`, `text` structured output; ignores temperature/top_p/max_output_tokens [49] |
| MCP | Official `@brave/brave-search-mcp-server` (npx or `docker.io/mcp/brave-search`), stdio or HTTP, 8 tools incl. `brave_web_search`, `brave_news_search`, `brave_llm_context`, `brave_summarizer` [6] | Remote `https://mcp.tavily.com/mcp/` with OAuth (`claude mcp add tavily-remote-mcp --transport http https://mcp.tavily.com/mcp/`), or `npx -y tavily-mcp`; tools `tavily-search`, `tavily-extract` [20] | Hosted `https://mcp.exa.ai/mcp` — **keyless free tier**, OAuth via `?login`, or `x-api-key`; tools `web_search_exa`, `web_fetch_exa`, `web_search_advanced_exa`, `agent_run`; Claude Code: `claude plugin install exa@claude-plugins-official` [34] | Hosted `https://search.parallel.ai/mcp` (keyless → `fast` mode, lower limits) and `/mcp-oauth`; `claude mcp add --transport http "Parallel-Search-MCP" https://search.parallel.ai/mcp`; tools `web_search`, `web_fetch`; excerpts capped ~25k chars/call [46] |
| Batch API | No | No (batch is the 20-URL `extract`) [18] | No | Task Group API (bulk async runs), Ingest API [58] |
| Structured outputs | No | `research` accepts `output_schema` JSON Schema [19] | `contents.summary` with JSON schema; `SearchSynthesisResponse` [31][32] | Task API and Responses API structured outputs [49][58] |
| Tool use / agent loop | Consumer of tools only | `research` endpoint is an agent | Agent runs (`/agent/runs`), effort tiers [30][33] | Task API (10 s–2 h), Responses API with `web_search` + up to 10 `mcp` tools [49] |
| Computer-use / browser agent | No | No | No | "Browser Use" integration listed [58] |
| Scheduled / automated | No | No | **Monitors** ($15/1k) [30] | **Monitor API** ($3–$10/1k checks, webhooks) [42][58] |
| Memory / workspaces | No | No | Websets | Memory API, organization roles [58] |
| Messaging (Telegram/Slack/…) | None | None | None | Zapier, n8n, Superhuman listed [58] |
| IDE plugins | Claude Desktop guide, Dify, n8n guides [10] | Cursor/Claude Desktop MCP configs [20] | Claude Code plugin, Cursor MCP, Claude connector directory [34] | Claude Code plugin (`/plugin marketplace add parallel-web/parallel-agent-skills`), Cursor plugin, OpenCode plugin, OpenClaw skills, LiteLLM, OpenRouter, LangChain, Ollama tool calling [48][58] |

## 3. Headless / server automation fit

All four are API-key, non-interactive, and run fine from launchd on macOS. Differences that matter for this server:

**Auth modes.**
- Brave: API key only, from the dashboard; the OpenClaw guide recommends setting a *usage limit* in the dashboard so the $5 monthly credit cannot be exceeded [8]. No OAuth, no device login.
- Tavily: API key (`tvly-…`) for REST; the remote MCP supports OAuth in Claude Code; "Agent Keys" are a ToS-defined auth option: a key Tavily "may make available" that lets a customer's agents use the Services "without requiring separate registration or the creation of an Account" — any use through it creates an Account bound by the full terms, the key is non-transferable, Tavily can revoke it without notice, and the customer is responsible for everything done through it; no public docs page describes how to obtain one (docs.tavily.com/documentation/agent-keys 404) [20][24]. Two key classes: **development keys (100 RPM)** and **production keys (1,000 RPM) — production keys require a paid plan or PAYGO enabled** [16].
- Exa: API key; hosted MCP is usable **without any key** (rate-limited free tier) or with OAuth [34].
- Parallel: API key; `parallel-cli login --device` for headless/SSH boxes; hosted MCP usable keyless in `fast` mode [46][47]. Also exposes an Account/Service API (`get-balance`, `create-key`) so a job can check remaining balance programmatically [58].

**Consumer subscriptions used programmatically.** Not applicable — none of the four has a consumer subscription; all are API products. The subscription-shaped options in this space are (a) Claude Code's built-in WebSearch under the Max plan (already how the Claude lanes work; withheld under third-party base URLs per the task's focus notes), (b) Ollama Pro/Max ($20/$100 per month with $60/$300 usage credits; a $500 Team plan with $1,000 credits also exists) whose `web_search`/`web_fetch` endpoints need an Ollama account key; Ollama's docs publish no separate search quota or price [68][69], and (c) Tavily's "Project" monthly plan (from 4,000 credits/month; $30–$500/month, $0.0075→$0.005 per credit) [14][15].

**Terms that bite an automated research server.**
- Brave: customer "shall not… store, cache, or create a database of Search Results… other than transient storage required for operation", may not use results "to create, evaluate, train, re-train, fine-tune, benchmark or otherwise improve artificial intelligence models", may not redistribute, may not bypass rate limits by creating multiple accounts [7]. A Jan 2026 HN thread asked whether the free tier's "no AI inference" wording forbids agent use; the answer in the thread was to cancel the free plan and "sign up for an AI plan instead" (Brave's plan names have since consolidated to Search/Answers; Brave's current OpenClaw guide names the *Search* plan, which includes the $5 credit) [11][8]. Brave's own guides for Claude Desktop, Claude Cowork and OpenClaw all use the Search plan [8][9].
- Exa: restrictions on "download, modify, copy, distribute… any information contained on, or obtained from or through, the Services, except for temporary files… cached by your web browser", plus a perpetual, irrevocable license to Exa over "User Input and Output"; no use "to develop any competitive product" [36] (the clause text is confirmed from the PDF; the §1.1/§1.2(c)/§4.2 numbering cited in [36] is unverified as of 2026-09-24). simonw raised exactly this "which rules am I subject to" concern about Brave and Exa in the Ollama thread [61].
- Tavily: Tavily may "use, process, analyze, and retain Customer Input… for purposes of training, improving… artificial intelligence models"; no account sharing; no resale. No explicit no-caching clause found [24].
- Parallel: the page at `/terms-of-service` reads as website terms (no scraping of parallel.ai, no storing "Content") and contains nothing specific about API result retention or training [56]; API-specific terms not found — searched: parallel.ai/terms (404), docs.parallel.ai llms.txt index (no terms page) [58]; re-read 2026-09-24 and the website-only reading stands, but a DPA/API terms page may exist behind login (unverified as of 2026-09-24).

**Rate limits and caps (defaults).**

| | Brave | Tavily | Exa | Parallel |
|---|---|---|---|---|
| Search | 50 QPS (Search plan); Answers 2 QPS; suggest/spellcheck 100 QPS [2] | 100 RPM dev / 1,000 RPM prod [16] | 10 QPS `/search`, `/answer`; 5 QPS deep; 100 QPS `/contents`; 25 QPS after $1k credits in 30 days [33] | 600 RPM search & extract; 2,000 RPM tasks; 300 RPM monitor and chat (the Responses API is not named on the rate-limit page, so "300 RPM responses" is inferred — unverified as of 2026-09-24); FindAll 300/h [45] |
| Research/agents | n/a | `research` 20 RPM; `crawl` 100 RPM; usage endpoint 10 per 10 min [16] | 5 QPS + 50 concurrent agent runs [33] | GETs don't count; contact support@parallel.ai for more [45] |
| Monthly cap | Set your own usage limit in dashboard [8] | 1,000 free credits/month; HTTP 432 = plan limit, 433 = PAYGO limit [15][19] | Free balance resets to $10 on the 1st [30] | "Up to 5,000 requests monthly at no cost" ($5 recurring credit) [41] |

**Data retention / query logging / ZDR.**
- Brave: SOC 2 Type II; data used only "for the narrow purposes documented in our Data Processing Addendum"; **Zero Data Retention** ("no queries are retained for any length of time") is enterprise-plan-only, enabled via API support; Brave claims to be "the only search API that can offer true Zero Data Retention" [1][78].
- Tavily: privacy policy says query data (and uploaded documents) is collected and, unless a contract says otherwise, "we may use certain portions of your query data to improve our responses to future queries"; retention is "for as long as you maintain an account" or until a valid deletion request; no ZDR option published [75]; the ToS additionally allows training on Customer Input [24].
- Exa: privacy policy states "Query Data is used to improve our products and technology, including by training and fine-tuning models that power our Services"; no retention period, logging statement or ZDR option published [76].
- Parallel: no query-logging or ZDR statement for the default endpoint; the only concrete retention clause is for the EU endpoint — "Search API requests sent to the EU endpoint are processed and served within the European Union, and we do not retain request or response content" [77]. No training clause found in the privacy policy or website ToS [56][77].

**Latency (published figures).** Only Parallel quantifies latency: `turbo` ~200 ms, `fast` ~700 ms, `basic` ~1 s, `advanced` ~3 s [43]. Tavily publishes only a relative ordering (`ultra-fast` lowest → `fast` → `basic` → `advanced` highest) and a sizing example that assumes ~3 s average latency [17][21]. Exa describes `instant` as "optimized for minimum response time" (autocomplete/voice), `fast` as "reduced latency" for user-facing search, and gives one number: `deep-lite` at a "consistent 4-second latency" [31]. Brave publishes no numbers, only a claim to "lowest latency among leading search APIs" per an unnamed third-party evaluation [1]. The Telegram-chat recommendation in §7 therefore rests on Parallel's figures alone.

**Sandboxing.** None run your code; Parallel's Task API and Exa's agent runs run *their* agents. No sandbox concerns beyond untrusted web content entering prompts.

**Structured event output.** Tavily `research` and Exa search both stream SSE (`text-delta`, `grounding`, `results`, `done`, `error` chunks for Exa) [19][31]; Parallel streams Task/FindAll/Responses events and supports webhooks [58]; Brave Answers streams [1]. Every vendor returns `request_id`/`search_id` and (Exa) `costDollars`, (Parallel) `usage[]`, (Tavily) `usage` per response when `include_usage=true` (`request_id` is always present) — good for audit-log lines [17][31][44].

**Session resume.** Parallel Responses API `previous_response_id`; Parallel Task runs are retrievable by run id; Tavily `research` returns `request_id` + `status: pending` for polling [19][49][58]. Brave and Exa search are stateless.

## 4. Cost

### 4a. Plan tiers (there are no consumer tiers; these are the API plans)

**Brave** [1][2]
- Search: $5.00 / 1k requests, $5 free credit every month, 50 QPS. Includes web/news/images/videos, "LLM context optimization", Goggles reranking, extra snippets.
- Answers: $4.00 / 1k + $5.00 / 1M input + $5.00 / 1M output tokens, $5 free credit/month, 2 QPS.
- Spellcheck & Autosuggest: $5 / 10k requests each, $5 credit/month, 100 QPS.
- Enterprise: custom (ZDR, NDAs, invoicing).

**Tavily** [14][15][18][19]
- Researcher (free): 1,000 credits/month, no card.
- Pay-as-you-go: $0.008 / credit.
- Project: monthly plans $30–$500 at $0.005–$0.0075 / credit, starting at 4,000 credits/month (so ~$30 ≈ 4,000 credits — derived from $30/4,000 and $500/100,000 on the api-credits page; the tavily.com/pricing slider read back ~$0.003/credit at 4,000 credits, which could not be reconciled — unverified as of 2026-09-24, verify in the dashboard).
- Credit table: basic search 1; advanced 2; extract basic 1 per 5 URLs, advanced 2 per 5 URLs (failures free); map 1 per 10 pages; crawl = map + extract; research `pro` 15–250, `mini` 4–110 credits per request.
- Student plan free. Enterprise custom.

**Exa** [29][30][32]
- Free: $10 credit on signup, resets to $10 on the 1st of every month ("around 1,400 searches"); no payment method needed.
- Search $7 / 1k (up to 10 results; +$1 / 1k extra results). Deep-lite $12, deep $12, deep-reasoning $15 per 1k.
- Contents $1 / 1k pages per content type; AI summaries $1 / 1k pages. Contents requested on a search call (text/highlights/summary) are included at no extra charge for up to 10 results per search, $1/1k pages beyond that [32]; the standalone $1/1k pages price applies to the `/contents` endpoint and to results past 10 [30].
- Answer $5 / 1k. Monitors $15 / 1k. Agents: minimal $0.012 … xhigh $1.00 per request; metered $0.10 / ACU + $0.005 / search call.
- Rate limit doubles to 25 QPS after $1,000 credits in 30 days [33].

**Parallel** [41][42][43]
- Free: up to $80 signup bonus + $5 / month recurring ("up to 5,000 requests monthly at no cost"); startup program up to $250.
- Search: turbo $1, fast $1, basic $5, advanced $5 per 1k (10 results included; extra results $1 / 1k).
- Extract $1 / 1k URLs. Task: lite $5, base $10, core $25, core2x $50, pro $100, ultra $300 … ultra8x $2,400 per 1k successful runs (failed runs unbilled). Responses: low $10, medium $50, high $250 / 1k. Monitor lite $3, base $10 / 1k. FindAll: preview $0.10/run (testing); base $0.25/run + $0.03/match; core $2/run + $0.15/match; pro $10/run + $1/match. Entity Search extra results $0.05/1k. Entity Search $5 / 1k.

**Reference points from LLM vendors** (why this doc exists): Perplexity Search API $5 / 1k standard or $1 / 1k `fast` tier, per successful request with no token costs; Perplexity's Sonar *models* additionally bill a per-request search fee of $5–$14 / 1k by search-context size (Sonar $5/$8/$12 low/medium/high; Sonar Pro and Sonar Reasoning Pro $6/$10/$14) on top of tokens [64]; Anthropic web search $10 / 1k plus tokens [65]; OpenAI web search $10 / 1k calls, search-content tokens billed at model rates for reasoning models [66]; Gemini 3.x grounding $14 / 1k with 5,000 free requests/month, Gemini 2.5 $35 / 1k with 1,500 RPD free [67].

### 4b. Monthly cost to run 10 / 100 / 1000 agent jobs

Assumptions (stated because search APIs bill per call, not per token): the task's ~150k-input / ~15k-output token job is modeled as a **research-class job = 20 searches + 10 page fetches**; cheaper modes used where the vendor has one (Tavily `basic`, Exa `auto`, Parallel `fast`); free credits applied; LLM tokens are billed by the LLM lane and excluded here. "Subscription" column = the only subscription-shaped path that exists for each vendor.

| Vendor | Per-job cost (list) | 10 jobs | 100 jobs | 1,000 jobs | (a) Subscription path |
|---|---|---|---|---|---|
| Brave Search plan | 20 × $0.005 = $0.10 (fetches self-hosted) | $1.00 → **$0** (within $5 credit) | $10 → **$5** | $100 → **$95** | none; Brave has no sub |
| Tavily (basic + extract) | 20 + 2 = 22 credits ≈ $0.176 PAYG | 220 cr → **$0** (1,000 free) | 2,200 cr → **$9.60** PAYG (1,200 paid) or ≈$30 Project plan | 22,000 cr → **$168** PAYG; ≈$110–$165 on a Project tier (derived from $0.005–$0.0075) | Project plan $30–$500/mo [14] |
| Exa (auto + contents) | 20 × $0.007 = $0.14 (contents on ≤10 results included) | $1.40 → **$0** ($10 credit) | $14 → **$4** | $140 → **$130** | none |
| Parallel `fast` + extract | 20 × $0.001 + 10 × $0.001 = $0.03 | $0.30 → **$0** | $3 → **$0** ($5 credit; the up-to-$80 bonus covers ~2,600 more jobs once) | $30 → **$25** | none |
| Parallel `advanced` + extract | 20 × $0.005 + 10 × $0.001 = $0.11 | $1.10 → **$0** | $11 → **$6** | $110 → **$105** | none |
| *Compare:* Anthropic web search | 20 × $0.010 = $0.20 + tokens | $2 | $20 | $200 | Claude Max: included in Claude Code lanes only |
| *Compare:* Perplexity Search API (standard) | 20 × $0.005 = $0.10 | $1 | $10 | $100 | none for the API |
| *Compare:* Perplexity Search API (`fast`) | 20 × $0.001 = $0.02 | $0.20 | $2 | $20 | none for the API |

Takeaways: at ≤100 jobs/month every one of the four is effectively free; at 1,000 jobs/month Parallel `fast` is ~4× cheaper than Brave and Perplexity's standard tier (Perplexity's `fast` tier matches it at $1/1k) and ~8× cheaper than Anthropic/OpenAI per search. Tavily is the most expensive of the four at volume unless you buy a Project tier. Numbers are list prices as of 2026-09-24; Exa's own team has admitted its pricing "has evolved to be confusing" [38].

## 5. Strengths & weaknesses per reviews

No independent public benchmark (LMArena-style) covers search APIs; the vendors' own benchmark pages were either unreachable or methodology-only (Parallel: "a bad benchmark can mislead you as much as no benchmark… vary only the search tool" [71]; Parallel's Extract blog claims highest recall on FinanceBench's 136 questions but publishes no competitor numbers [55]; Exa's docs cite no benchmarks [31]). Not found — searched: parallel.ai/blog/introducing-parallel-search-api, parallel.ai/blog/search-api-benchmarks, docs.parallel.ai/search/evaluating-search.md, exa.ai/docs/reference/how-exa-search-works. What follows is practitioner sentiment.

**Brave**
- Best at: broad, Google-like general coverage from an independent index; the Telem gateway author (routes across Exa/Parallel/Tavily/Brave/SerpAPI/…) says Brave has "strong general internet coverage, but might not be the best for domain-specific queries like financial research" [60]. Positioned by HN commenters as the drop-in for Google Custom Search [12]; Google's own page confirms the Custom Search JSON API "is closed to new customers" and existing customers "have until January 1, 2027 to transition", with Vertex AI Search (≤50 domains) as the suggested replacement [72]. Ollama's maintainer lists Brave among "decent privacy-preserving vendors" [61].
- Weak at: it returns SERP snippets, not page content, so agents need a second fetch step; Tavily's (vendor) comparison says it "may introduce noise" and lacks accuracy for multi-hop questions [25]. Terms are the strictest on storage/training [7], and the free-tier "no AI inference" wording confused users into a Jan 2026 HN thread [11].
- Reliability: status page shows all services online but marks the Search API as "not monitored" and publishes no 90-day history [13]. Controversy: pricing/plan restructuring since the 2023 launch (three "Data for Search / AI / Storage" categories then; Search/Answers now) [12][1].

**Tavily**
- Best at: agent-ready snippets in one call (`include_answer`, `raw_content`, `chunks_per_source`), `news`/`finance` topics, an `extract` that batches 20 URLs, and the lowest-friction free tier (1,000 credits, no card) [15][17][18]. Its own Sep 2026 comparison claims it "balances latency, accuracy, and information density" — vendor claim [25]. Enterprise references: IBM CUGA, BMO AML screening [26].
- Weak at: most expensive of the four per call at volume (§4b); production RPM gated behind paid/PAYGO [16]; terms let Tavily train on your inputs [24]; only 2 tools on the remote MCP [20] (the local `npx tavily-mcp` server may expose more, e.g. map/crawl — unverified as of 2026-09-24). Scry's author lumps "Google Search, Tavily, Exa" together as fixed-price black boxes that map agent context to "a tiny subset of their index" [63].
- Reliability: 100% uptime Jun–Sep 2026 for API, MCP and website; no incidents [28]. Controversy: none found beyond the Nebius acquisition (Feb 2026, $275M), which drew almost no HN discussion [27].

**Exa**
- Best at: semantic/entity search — "particularly strong for entity and people search" [60]; commenters found it surfaced "the exact stuff I needed and recent, up-to-date stuff" for technical queries better than Google [38]; Launch HN (412 points) praised the "airtable-like" Websets UI [37]. Rich content controls (`highlights.query`, JSON-schema summaries, `maxAgeHours`, subpages) [32]. Free keyless MCP is the easiest zero-config grounding for any MCP client [34].
- Weak at: "can be bad at latest news" [60]; Tavily's comparison says results "may lack freshness" [25]. Launch HN complaints: Websets stuck "Verifying…" for minutes, ~30/70 relevance on a GitHub-repo query (mdaniel), price-filter misunderstanding (theamk), 750 free credits burned on one search and no sub-$10 plan (vetleen, ixxie) [37]. Pricing confusion acknowledged by an Exa employee in Sep 2025 [38]. A Jan 2026 HN submission alleges Exa indexes personal sites "ignoring robots.txt" (linked tweet unreachable; 1 point, no discussion — unverified as of 2026-09-24) [39]; robots.txt questions were also raised at launch [37].
- Reliability: 90-day uptime Search API 99.97%, Websets 99.99%, MCP 100%, Agents 99.92% [40].

**Parallel**
- Best at: price/latency — `fast` at $1/1k, ~700 ms, excerpts pre-extracted so one call replaces search+fetch [43][44]; "performing well under high concurrency" [60]; the deepest automation surface (Task API up to 2 h runs, Monitor, FindAll, webhooks, SSE, CLI `--json`, device login, Claude Code plugin) [47][48][50][58]. Tavily's own comparison concedes it fits "complex investigation requiring orchestrated research steps" [25].
- Weak at: youngest vendor (Search API only reached GA within the year [58]); default mode is the $5/1k `advanced`, so unconfigured callers pay 5× [43]; no public benchmark numbers [71]; a Sep 2026 HN "AI bot traffic is out of control" thread names "parallel web systems" among aggressive crawlers [59]; website terms silent on API result retention [56]. Tavily (vendor) says its breadth "may exceed retrieval-focused needs; variable costs" [25].
- Reliability: status page all operational, six components, no incidents listed Jun–Sep 2026, no uptime percentages published [57].

**Cross-cutting community view.** The "Ask HN: free MCP for web search?" thread (Jan 2026) rejected Exa and Brave MCPs as pay-per-use and landed on self-hosted fetchers [62] — note that both now have free tiers/keyless MCPs [34][46]. The Ollama thread's consensus: hosted APIs beat local SearXNG on quality and blocking, but the terms (Brave no-store, Exa no-download) create legal ambiguity for downstream storage [61]. Reddit and X could not be fetched in this session (not found — searched: reddit.com/r/LocalLLaMA search JSON → blocked; twitter.com status for [39] → not fetchable).

## 6. Finance / trading relevance

- **Real-time market data:** none of the four is a market-data provider; they return web pages/news. Brave's `web/rich` / `enable_rich_callback=1` returns "rich results (weather, stocks, sports)" cards — useful for a quick quote sanity check, not for a feed [3][4]. Keep Alpaca/Tradier as the price source.
- **Finance-tuned search:** Tavily `topic: "finance"` (alongside `news`) and `time_range` [17]; Exa `category: "financial report"` targets filings, plus `news`/`company` categories and `startPublishedDate` [31]; Parallel `source_policy.after_date` + include-domains (e.g. `sec.gov`, `investor.*`) and Extract validated on FinanceBench-style SEC/earnings documents [51][55]; Brave `news/search` with `freshness=pd` and `count` up to 50 [5].
- **Sentiment sources:** Exa's `people`/`personal site` categories reach blogs and posts; nobody here offers X/Reddit firehoses. Telem's author explicitly flags Brave as weak for financial research and Exa as weak on latest news [60], which argues for Tavily/Parallel for the momentum-lab news scan and Exa for filings/entity discovery.
- **Monitoring products (fit the Atlas advisors/governor loops):** Exa Monitors ($15/1k) [30]; Parallel Monitor API ($3–$10/1k checks, webhooks, follow-up Task runs) [42][58]. Parallel FindAll can build "every company that…" lists with enrichment ($0.25/run + $0.03/match at the base tier) [42].
- **Restrictions:** Brave's no-storage clause [7] and Exa's no-download clause [36] mean the Atlas ledger should persist *your own notes, URLs and citations*, not verbatim result payloads; Tavily/Parallel terms as read do not restrict this, but Parallel's API terms were not found. None of the four provides investment advice or order routing, so the server's "no live order path" rule is unaffected.

## 7. Integration recipe for our server

**Recommendation.** Add one thin `search_provider` abstraction with three backends, chosen per lane by env:

1. **Parallel `fast` (default for DeepSeek/GLM/Kimi/Qwen/MiniMax/Ollama/Cursor lanes).** Cheapest, sub-second, excerpts pre-extracted, $5/month credit + up-to-$80 bonus, keyless MCP for zero-config lanes, device-login CLI for the Mac Mini [41][43][46][47].
2. **Tavily (news/finance lanes and as fallback).** `topic="finance"|"news"`, 1,000 free credits/month, remote MCP with OAuth in Claude Code [15][17][20].
3. **Exa (entity/filing discovery, adversarial review evidence).** `category="financial report"|"company"`, JSON-schema summaries, keyless MCP; $10/month free [30][31][34].
4. **Brave** only if you need Google-like breadth or the news index; treat results as transient and never store raw payloads [7]. Not recommended as the default because of terms and the extra fetch hop.

**Auth / secrets.** Put `PARALLEL_API_KEY`, `TAVILY_API_KEY`, `EXA_API_KEY` in the existing `env_files` plumbing; set dashboard usage limits (Brave) and check balance via Parallel's `get-balance` service endpoint in a weekly governor job [8][58]. Never put keys in MCP URLs (Tavily's `?tavilyApiKey=` form leaks into logs) — use OAuth or headers [20].

**MCP wiring for Claude Code lanes** (these register at the user scope on the Mac Mini):

```bash
claude mcp add --transport http "Parallel-Search-MCP" https://search.parallel.ai/mcp   # keyless = fast mode
claude mcp add tavily-remote-mcp --transport http https://mcp.tavily.com/mcp/          # OAuth on first use
claude plugin install exa@claude-plugins-official                                        # hosted, keyless free tier
```
Sources: [46][20][34]. For a third-party-base-URL lane that runs Claude Code, pass the same servers via `--mcp-config` in the job payload so the agent has `web_search`/`web_fetch` tools even though built-in WebSearch is withheld.

**Python sketch** (`src/runner/search_provider.py`, sync; all three SDKs also ship async clients [23][35][54]):

```python
import os
from dataclasses import dataclass

@dataclass
class Hit:
    url: str; title: str; snippet: str; published: str | None; provider: str

def search(query: str, *, provider: str | None = None, n: int = 8,
           topic: str = "general", after: str | None = None) -> list[Hit]:
    provider = provider or os.environ.get("SEARCH_PROVIDER", "parallel")
    if provider == "parallel":                                    # $1/1k fast [43]
        from parallel import Parallel
        c = Parallel(api_key=os.environ["PARALLEL_API_KEY"])
        r = c.search(objective=query, search_queries=[query], mode="fast",
                     max_results=n, max_chars_per_result=1500)
        return [Hit(x.url, x.title, " ".join(x.excerpts), x.publish_date, "parallel")
                for x in r.results]
    if provider == "tavily":                                      # 1 credit basic [15]
        from tavily import TavilyClient
        r = TavilyClient(os.environ["TAVILY_API_KEY"]).search(
            query, search_depth="basic", topic=topic, max_results=n,
            include_published_date=True, start_date=after)
        return [Hit(x["url"], x["title"], x["content"], x.get("published_date"), "tavily")
                for x in r["results"]]
    if provider == "exa":                                         # $7/1k auto [30]
        from exa_py import Exa
        r = Exa(os.environ["EXA_API_KEY"]).search(
            query, type="auto", num_results=n, start_published_date=after,
            contents={"highlights": {"max_characters": 1500}})
        return [Hit(x.url, x.title, " ".join(x.highlights or []), x.published_date, "exa")
                for x in r.results]
    raise ValueError(provider)
```
(Method names follow the SDK READMEs [23][35][54]; the search quickstart and the beta→GA migration guide both use `client.search(search_queries=[...], mode=...)` against GA `/v1/search`; the `beta` namespace maps to the legacy `/v1beta/` endpoints, which are for existing integrations only [44][51].) Log `request_id`/`search_id` and the provider's `usage`/`costDollars` field into the job's audit JSONL [17][31][44].

**CLI-only alternative for shell-driven skills:** `parallel-cli search "query" --json` (exit 3 = auth error, 5 = timeout) after a one-time `parallel-cli login --device` [47].

**Task-class fit.**

| Task class | Fit | Why |
|---|---|---|
| Research (alpha-lab scout, momentum-lab news) | Parallel fast / Tavily news+finance | cheapest per call; freshness filters; excerpts ready [17][43] |
| Coding | Exa (keyless MCP `web_search_exa`/`web_fetch_exa`) or Parallel MCP | docs/blog retrieval; HN reports Exa beats Google on technical queries [38] |
| Code review | Parallel `advanced` is pitched for "code review work" [43]; usually no search needed | |
| Chat (Telegram) | Parallel turbo/fast (~200–700 ms) [43]; Tavily `ultra-fast`/Exa `instant` are the unquantified alternatives [17][31] | latency — Parallel is the only vendor with published numbers (§3) |
| Classification / routing | none — no search needed | |
| Adversarial review (governor, advisors panel) | Exa `financial report` + Tavily `finance` for independent evidence [17][31] | two indexes reduce single-source bias (Tavily's own "standalone vs integrated" post makes the same point [26]) |
| Trading research / deep dives | Parallel Task API `core`/`pro` ($25–$100/1k runs, 1–10 min) with `output_schema`, or Tavily `research` (`mini` 4–110 credits) [15][42][50] | async, schema'd, cheap relative to running an LLM lane for 10 minutes |

**Gotchas.**
- Parallel's default `mode` is `advanced` ($5/1k, ~3 s) — always set `mode="fast"` unless you want depth [43]; `fast` only reached GA on 2026-08-21, so expect its behaviour to move [74]. Keyless MCP forces `fast` with lower limits [46].
- Tavily production keys (1,000 RPM) need a paid/PAYGO plan; dev keys are 100 RPM and `research` is 20 RPM [16]. Check `failed_results` on extract even with HTTP 200 [18]. HTTP 432/433 are plan-limit codes, not 429 [19].
- Exa: `category="research paper"`, `pdf`, `github`, `tweet` are deprecated (use `publication`) and `startCrawlDate`/`endCrawlDate` are ignored — use `startPublishedDate` [31][73].
- Exa deep modes are 5 QPS and `deep-reasoning` costs $15/1k; `numResults>10` adds $1/1k; contents beyond 10 results per search or via `/contents` are $1/1k pages [30][32][33]. Exa terms forbid storing/distributing retrieved info [36].
- Brave: `count` max 20 web / 50 news, `offset` max 9; no page-content endpoint verified (LLM Context docs 404); terms forbid caching results and using them to improve AI models [4][5][7]. Set a dashboard usage limit before automating [8].
- All four: results are untrusted content — keep the existing prompt-injection guards in front of anything that lands in a Telegram reply or a ledger.

## 8. Verdict

1. For the "bring your own search" lanes, Parallel `fast` is the price/latency winner at $1/1k with $5/month free and an up-to-$80 bonus — roughly 5–10× cheaper than Perplexity standard/Anthropic/OpenAI/Gemini grounding per search (Perplexity's `fast` Search tier is also $1/1k, so on price alone the two are tied) [41][43][64][65][66][67].
2. Tavily is the safest second backend: finance/news topics, 1,000 free credits/month, OAuth remote MCP in Claude Code, 100% recent uptime, but the priciest of the four at volume [15][20][28].
3. Exa is the specialist for entities, filings and semantic discovery with a keyless MCP, but is weak on breaking news and its terms forbid storing results [34][36][60].
4. Brave gives Google-like breadth but is results-only, no-cache/no-training terms, and confusing plan history; use it sparingly and never persist payloads [1][7][11].
5. The Perplexity-as-grounding recommendation should be downgraded: at ≤100 jobs/month all four are free, and at 1,000 jobs/month Parallel+Tavily together cost less than Perplexity's standard $5/1k Search API alone (§4b), though Perplexity's `fast` tier at $1/1k is price-competitive with Parallel `fast` — the downgrade rests on freshness/finance features and free tiers, not price.

Fit scores (1–10):

| | Research | Coding/agentic | Cost efficiency | Automation friendliness | Trading research |
|---|---|---|---|---|---|
| Brave | 6 | 5 | 6 | 6 | 4 |
| Tavily | 8 | 6 | 6 | 8 | 7 |
| Exa | 7 | 8 | 7 | 8 | 7 |
| Parallel | 8 | 8 | 9 | 9 | 7 |

## 9. Sources

All accessed 2026-09-24.

1. https://brave.com/search/api/
2. https://api-dashboard.search.brave.com/app/plans
3. https://api-dashboard.search.brave.com/app/documentation/web-search/get-started
4. https://api-dashboard.search.brave.com/app/documentation/web-search/query
5. https://api-dashboard.search.brave.com/app/documentation/news-search/get-started
6. https://github.com/brave/brave-search-mcp-server
7. https://api-dashboard.search.brave.com/terms-of-service
8. https://brave.com/search/api/guides/use-with-openclaw/
9. https://brave.com/search/api/guides/claude-cowork-amazon-bedrock-brave-mcp/
10. https://brave.com/search/api/guides/
11. https://news.ycombinator.com/item?id=46822822
12. https://hn.algolia.com/api/v1/search?query=%22brave%20search%20api%22&hitsPerPage=20 (incl. items 36140371, 47170182, 45744078, 44586242)
13. https://status.brave.app/
14. https://www.tavily.com/pricing
15. https://docs.tavily.com/documentation/api-credits
16. https://docs.tavily.com/documentation/rate-limits
17. https://docs.tavily.com/documentation/api-reference/endpoint/search
18. https://docs.tavily.com/documentation/api-reference/endpoint/extract
19. https://docs.tavily.com/documentation/api-reference/endpoint/research
20. https://docs.tavily.com/documentation/mcp
21. https://docs.tavily.com/documentation/best-practices/best-practices-search
22. https://docs.tavily.com/documentation/quickstart
23. https://github.com/tavily-ai/tavily-python
24. https://www.tavily.com/terms
25. https://www.tavily.com/blog/tavily-vs-exa-vs-parallel-vs-firecrawl-vs-perplexity-vs-brave-choosing-the-right-web-search-api (vendor post, 2026-09-14)
26. https://www.tavily.com/blog
27. https://news.ycombinator.com/item?id=47024216
28. https://status.tavily.com/
29. https://exa.ai/pricing
30. https://exa.ai/docs/reference/pricing
31. https://exa.ai/docs/reference/search
32. https://exa.ai/docs/reference/contents-retrieval
33. https://exa.ai/docs/reference/rate-limits
34. https://exa.ai/docs/reference/exa-mcp
35. https://github.com/exa-labs/exa-py
36. https://exa.ai/terms (PDF, Exa Labs Terms of Service, §1.1, §1.2(c), §4.2)
37. https://news.ycombinator.com/item?id=43906841
38. https://news.ycombinator.com/item?id=45118788
39. https://news.ycombinator.com/item?id=46574182
40. https://status.exa.ai/
41. https://parallel.ai/pricing
42. https://docs.parallel.ai/getting-started/pricing.md
43. https://docs.parallel.ai/search/modes.md
44. https://docs.parallel.ai/search-api/search-quickstart
45. https://docs.parallel.ai/resources/rate-limits
46. https://docs.parallel.ai/integrations/mcp/search-mcp.md
47. https://docs.parallel.ai/integrations/cli.md
48. https://docs.parallel.ai/integrations/claude-code-marketplace.md
49. https://docs.parallel.ai/responses-api/openai-compatibility.md
50. https://docs.parallel.ai/task-api/guides/choose-a-processor.md
51. https://docs.parallel.ai/search/migrate-to-parallel.md
52. https://docs.parallel.ai/integrations/anthropic-tool-calling.md
53. https://docs.parallel.ai/resources/crawler.md
54. https://github.com/parallel-web/parallel-sdk-python
55. https://parallel.ai/blog/parallel-search-api (Extract / FinanceBench claims)
56. https://parallel.ai/terms-of-service
57. https://status.parallel.ai/
58. https://docs.parallel.ai/llms.txt
59. https://hn.algolia.com/api/v1/search?query=%22parallel%20web%20systems%22&hitsPerPage=15 (items 46859202, 49706090)
60. https://news.ycombinator.com/item?id=49469804
61. https://news.ycombinator.com/item?id=45381844
62. https://news.ycombinator.com/item?id=46657082
63. https://news.ycombinator.com/item?id=49748041
64. https://docs.perplexity.ai/getting-started/pricing
65. https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool
66. https://developers.openai.com/api/docs/pricing
67. https://ai.google.dev/gemini-api/docs/pricing
68. https://docs.ollama.com/capabilities/web-search
69. https://ollama.com/pricing
70. https://github.com/searxng/searxng
71. https://docs.parallel.ai/search/evaluating-search.md
72. https://developers.google.com/custom-search/v1/overview (Custom Search JSON API shutdown notice)
73. https://exa.ai/docs/changelog
74. https://docs.parallel.ai/resources/changelog.md
75. https://www.tavily.com/privacy
76. https://exa.ai/privacy-policy
77. https://parallel.ai/privacy-policy
78. https://brave.com/blog/search-api-zero-data-retention/
79. https://exa.ai/docs/reference/chat-completions
80. https://exa.ai/docs/reference/agent

Pages tried and not reachable (404/403/blocked), listed so a fact-checker does not repeat them: brave.com/search/api/terms/, api-dashboard.search.brave.com/documentation/llm-context/get-started (and /app/documentation/llm-context/*), /app/documentation/pricing, /app/documentation/guides/rate-limiting, npmjs.com/package/@brave/bx, github.com/brave/bx, parallel.ai/terms, docs.parallel.ai/integrations/mcp/parallel-search-mcp, parallel.ai/blog/introducing-parallel-search-api, parallel.ai/blog/search-api-benchmarks, exa.ai/docs/reference/exa-code, exa.ai/docs/reference/how-exa-search-works (returned an unrelated page), exa.ai/privacy (404; /privacy-policy works), docs.tavily.com/documentation/agent-keys (404), docs.parallel.ai/resources/data-residency.md (404), tavily.com/blog/introducing-ultra-fast-search (404), exa.ai/docs/reference/search-types (404), nebius.com/newsroom/nebius-to-acquire-tavily, openai.com/api/pricing (403), reddit.com (blocked), simpletechguides.com comparison (article body not served).

## Verification log (2026-09-24)

**Corrections applied from the fact-check: 14** — 6 major, 8 minor.
- Major (6): Perplexity Search API `fast` tier ($1/1k) added to §4a reference points, §4b table, §4b takeaways, §8 verdict items 1 and 5 (the "Parallel is 5–10× cheaper than Perplexity" claim now applies to Perplexity's standard tier only); Parallel SDK sketch in §7 changed from `c.beta.search` to `c.search` (GA `/v1/search`).
- Minor (8): §7 SDK note rewritten (quickstart + migration guide both use `client.search`); Exa contents-on-search pricing resolved (included for ≤10 results, $1/1k beyond) in §4a, §4b (Exa per-job $0.15 → $0.14) and §7 gotchas; Parallel free tier "up to $80" bonus; Parallel FindAll full tier ladder + Entity Search extra results; Exa agent effort/metered pricing in §1; Brave HN thread answer quoted faithfully in §3; Tavily `usage` only with `include_usage=true` in §3.

**Claims re-verified (source):**
- Perplexity Search API $5/1k standard, $1/1k fast, per successful request, no token costs; Sonar per-request search fees $5–$14/1k by context size — docs.perplexity.ai/getting-started/pricing [64].
- Exa Agent effort ladder $0.012–$1.00, metered `auto` ($5 cap) / `ultra` ($20 cap), `budget.maxCostDollars` $1–$100, $0.005 per search call, $0.10/ACU — exa.ai/docs/reference/agent [80].
- Exa changelog Jun 16 / Jun 24 / Jul 1 / Jul 23 / Aug 28 / Sep 24 2026 entries — exa.ai/docs/changelog [73]; `startCrawlDate`/`endCrawlDate` marked "Deprecated. Ignored by the API" and `publication` in the category list — exa.ai/docs/reference/search [31].
- Exa `/chat/completions` routes to `/answer`, `model: "exa"`, base URL `https://api.exa.ai` — exa.ai/docs/reference/chat-completions [79].
- Parallel changelog: Fast mode 2026-08-21; Responses API domain filters + `web_search_call` 2026-09-18; `mcp` tool + `data_sources` 2026-09-23 — docs.parallel.ai/resources/changelog.md [74]. Mode latencies turbo ~200 ms / fast ~700 ms / basic ~1 s / advanced ~3 s — docs.parallel.ai/search/modes.md [43].
- Parallel EU-endpoint no-retention clause — parallel.ai/privacy-policy [77].
- Tavily Agent Key definition, non-transferability, revocation — tavily.com/terms [24]; Tavily query-data use and retention — tavily.com/privacy [75]; Tavily `include_usage`/`request_id` and relative latency ordering — docs.tavily.com search endpoint + best-practices [17][21].
- Exa "Query Data is used to improve… including by training and fine-tuning models" — exa.ai/privacy-policy [76].
- Brave enterprise-only ZDR, "no queries are retained for any length of time" — brave.com/blog/search-api-zero-data-retention [78]; "lowest latency among leading search APIs" claim (no numbers) — brave.com/search/api [1].
- Google Custom Search JSON API closed to new customers, existing customers until January 1, 2027 — developers.google.com/custom-search/v1/overview [72].

**Stale / unverified flags left in place (marked "unverified as of 2026-09-24" inline):** Brave release-cadence dates (§1); Tavily Project per-credit range (§4a); Parallel "300 RPM responses" inference (§3); Brave `bx` CLI package source (§2); Parallel "$130M raised" (§1); Tavily local MCP tool count (§5); Exa robots.txt allegation [39] (§5); Exa ToS section numbering [36] (§3); Parallel API-specific terms possibly behind login (§3). Also noted: Ollama $500 Team plan added to §3.

**Not obtained:** absolute latency figures for Tavily, Exa (`instant`/`fast`/`auto`) and Brave — none are published; recorded as such in §3 rather than estimated.

**Fact-checker's overall quality rating: good.**
