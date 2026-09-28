# Direct open-weight inference hosts (Groq, Cerebras, Fireworks, Together, DeepInfra, SambaNova) incl. free tiers — research (as of 2026-09-24)

Scope: the six hosts that serve open-weight models from their own hardware, compared with the two "cheap open-weight lane" alternatives already in this research set (Ollama Cloud Pro and OpenRouter). All numbers are from vendor pages fetched 2026-09-24 unless marked. Web search was unavailable in this session (budget exhausted); every fact below comes from a directly fetched primary page, the OpenRouter/ArtificialAnalysis public endpoints, the HN Algolia API, or the in-repo comparison matrix (§9 #88). Numbers I could not confirm on a primary page are marked "(unverified)". Both the original session and the 2026-09-24 verification pass ran with web search unavailable (budget exhausted): every number is a single-day vendor-page snapshot with no independent sweep for newer announcements — re-run the "newer than doc" check with search enabled (unverified as of 2026-09-24).

Job-shape assumptions used throughout (§4): the lane under evaluation is **classification / routing / summarization**, not the agentic executor. ~1,500 jobs/month = 1,200 short calls (3k in / 0.3k out) + 300 summaries (10k in / 0.8k out) → **6.6M input + 0.6M output tokens/month, ~220k input tokens/day, ~50 calls/day, ≤2 concurrent**. The set's synthetic "full agent job" (150k in / 15k out) is shown as a second column only to make clear which hosts stop being free the moment the lane grows.

---

## 1. Snapshot

**Category.** Metered, pay-per-token APIs that run open-weight models (Apache-2.0 / MIT / model-specific licences) on the vendor's own fleet — either custom silicon (Groq LPU, Cerebras WSE-3, SambaNova RDU) or NVIDIA GPUs (Fireworks, Together, DeepInfra). All six expose an OpenAI-compatible `/v1/chat/completions`; none exposes an Anthropic-compatible `/v1/messages` (only Ollama Cloud does, §2). Three of the six have a genuine no-card free tier (Groq, Cerebras, SambaNova); the GPU shops are prepaid/postpaid metered from the first token.

**Candidates (exact products, 2026-09-24):**

| Host | Product name | Open-weight models served on the public/serverless tier today | Hardware |
|---|---|---|---|
| Groq | GroqCloud (Free / Developer / Enterprise plans) | `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `openai/gpt-oss-safeguard-20b`, `qwen/qwen3.8-27b` (preview), `minimaxai/minimax-m2.7` (preview, enterprise-priced), `llama-3.3-70b-versatile` / `llama-3.1-8b-instant` (enterprise-only since 2026-08-16), Whisper, Prompt Guard, Orpheus TTS [2][3] | LPU / LPX |
| Cerebras | Cerebras Inference (Free Trial / Developer / Enterprise) + Cerebras Code | `gpt-oss-120b`, `qwen-3.8-27b` on the public shared tier; `kimi-k2.7-code` (customer trials), `gemma-4-31b` (dedicated only) [13][16] | WSE-3 |
| Fireworks | Fireworks AI Serverless (Standard / Priority / Fast) | DeepSeek V4 Pro 0813, V4.1 Flash, V4 Flash 0731; Qwen3.8 Max, Qwen3.8 27B; GLM 5.3 + 5.3 Flash; Kimi K3, K2.7 Code; gpt-oss-120b; Muse Glimmer 30B (Meta, Apache-2.0); Llama 3.3 70B [24][26][33] | NVIDIA GPU |
| Together | Together AI Serverless | DeepSeek V4 Pro 0813 / V4.1 Flash / V4 Flash 0731; Qwen3.8-2.4T-A95B, Qwen3.8 Flash, Qwen3.7-Max/Plus, Qwen3.5 9B/397B; GLM-5.3 + Flash; Kimi K3; gpt-oss-120B; Llama 3.3 70B; MiniMax M3; Gemma 4 31B; Muse Glimmer 30B [35][39] | NVIDIA GPU |
| DeepInfra | DeepInfra (Standard 1× / Priority 1.5× / Flex 0.8× tiers) | DeepSeek V4 Pro / V4 Flash / V4 Flash 0731 / V3.2 / R1; Qwen3.8-2.4T-A95B, Qwen3.8 27B, Qwen3.6-35B, Qwen3.5 9B/397B, Qwen3-Max; GLM-5.3 / 5.3 Flash / 5.1; Kimi K3, K2.6; MiMo-V2.6-Pro / Flash; gpt-oss-120b; Llama 4 Scout; Gemma 4 31B; Nemotron 3; also resells Claude [47][48][49] | NVIDIA GPU |
| SambaNova | SambaCloud (Free / Developer / Enterprise) | Production: MiniMax-M2.7 (192k ctx), DeepSeek-V3.1 (128k), Llama-3.3-70B (128k), gpt-oss-120b (128k). Preview: MiniMax-M3 (1M ctx, text+image), DeepSeek-V3.2 (**32k** ctx), gemma-4-31B-it (128k) [58] — all comfortably hold the lane's 10k-token summaries, but the V3.2 preview is the only one where a long agent-shaped prompt would not fit | RDU |

**Positioning in one paragraph.** For this server the six split cleanly. **Groq and Cerebras** are the *fast-and-free* pair: both give a no-card tier that comfortably covers a 50-call/day classification lane on `gpt-oss-120b` (Cerebras 1M tokens/day; Groq 200k tokens/day per model), with the narrowest catalogues in the group (2 open chat models each on the free/public tier) and constrained-decoding `json_schema` on exactly those models. **DeepInfra** is the *cheapest metered catalogue*: the widest model list, zero-data-retention written into its ToS, and prices 3–4× below the field (`gpt-oss-120b` $0.037/$0.17; GLM-5.3-Flash $0.075/$0.25), at GPU speeds (36–227 tok/s) and with no free credits. **Fireworks and Together** are the *reliable-production GPU shops*: same list prices as the model vendors ($0.15/$0.50 GLM-5.3-Flash, $0.15/$0.60 gpt-oss-120b), 50 % batch, ZDR by default (Fireworks) or opt-in (Together), but no free tier (Together needs a $5 minimum buy; Fireworks gives $1 and 10 RPM without a card). **SambaNova** is fast (709 tok/s on gpt-oss-120b) but its free tier is 20 requests/day, its catalogue is the smallest and oldest (DeepSeek V3.1/V3.2, no Qwen3.8/GLM-5.3/Kimi K3), and HN chatter calls the company's 2025 Intel deal "a firesale" — a third-choice. Against the two incumbents: **Ollama Cloud Pro** ($20 → $60 credits, 19 models at list prices, `/v1/messages`, no logging) remains the best *subscription-shaped* open-weight lane, and **OpenRouter** remains the best *single key to all of the above* with `:free` variants gated at 50 req/day (<$10 lifetime) or 1,000 req/day ($10+). Ranked recommendation in §8.

---

## 2. Interfaces & surfaces

| Surface | Groq | Cerebras | Fireworks | Together | DeepInfra | SambaNova | Ollama Cloud | OpenRouter |
|---|---|---|---|---|---|---|---|---|
| Base URL | `https://api.groq.com/openai/v1` [8] | `https://api.cerebras.ai/v1` [18] | `https://api.fireworks.ai/inference/v1` (unverified — not on a fetched page) | `https://api.together.ai/v1` [38] | `https://api.deepinfra.com/v1/openai` (unverified) | per-key base URL shown on the API-keys page [60] | `https://ollama.com/v1` (OpenAI) + `https://ollama.com/v1/messages` (Anthropic) [64][65] | `https://openrouter.ai/api/v1` [72] |
| OpenAI chat completions | Yes | Yes | Yes | Yes (documented endpoint list; no Batch/Files/Assistants) [43] | Yes | Yes (`n` 1–8, `seed`, `logit_bias`, `top_k`; ignores presence/frequency penalty; no `system_fingerprint`) [60] | Yes | Yes |
| OpenAI Responses API | Yes, beta, incl. built-in browser search + code execution, MCP; no `previous_response_id`/`store` [8] | Not found | Yes (`store=True` default → 30-day retention; set `store=False`) [31] | Not listed in the compatibility matrix (Batch: not supported; Files: partial; Assistants: not implemented) [43] | Not found | Mentioned for gpt-oss-120b tool calling only [59] | No | Partial (unverified) |
| Anthropic `/v1/messages` | No | No | No | No [43] | No | No | **Yes** — Claude Code can be pointed at it (`ANTHROPIC_BASE_URL`, `OLLAMA_API_KEY` bearer); no token counting, no `tool_choice`, no caching, no batch [65] | No |
| First-party SDK | Python/TS (OpenAI-compatible) | `cerebras_cloud_sdk` (Py), `@cerebras/cerebras_cloud_sdk` (Node) [18] | Python/TS | `together` (Py), `together-ai` (TS) [38] | OpenAI SDK | OpenAI SDK [60] | `ollama` Py/JS + OpenAI/Anthropic clients [64] | OpenAI SDK |
| CLI | None (console only) | None | `firectl` (unverified) | None | None | None | `ollama run <model>:cloud`, `ollama launch claude` [64][88] | None |
| Auth | Bearer API key; org-level limits [1] | Bearer `CEREBRAS_API_KEY` [18] | Bearer key; account-wide RPM envelope [27] | Bearer key; prepaid balance [37] | Bearer key | Bearer key | `OLLAMA_API_KEY` bearer [64] | Bearer key; `free_model_daily_requests` readable from `GET /api/v1/key` [72] |
| Rate-limit visibility | `x-ratelimit-remaining-{requests,tokens}`, `x-ratelimit-reset-*`, `retry-after` on 429 [1] | 429 + support page [18] | 429; adaptive TPM [28] | 429 with reset guidance; **dynamic, unpublished** limits [36] | 429 on >200 concurrent [50] | 429 (unverified headers) | usage page `ollama.com/settings/usage` [64] | `X-RateLimit-*` + `Retry-After` [72] |
| Web UI / playground | Console + GroqChat | Console (status-tracked component) [23] | Console | Playground (stores history unless ZDR) [44] | Dashboard | Playground | ollama.com + local app | Chat UI |
| Mobile reach | None first-party (API only) | None | None | None | None | None | Ollama desktop app only (unverified for mobile) | None |

Interfaces are otherwise identical from Python: one `openai.OpenAI(base_url=..., api_key=...)` per host. The only surfaces that matter for this server's "ease across interfaces" preference are (a) Ollama's Anthropic endpoint, which lets the existing Claude Agent SDK / Claude Code tooling drive an open model unchanged, and (b) OpenRouter's single key. None of the six direct hosts offers either.

---

## 3. Headless / server automation fit

**Non-interactive use.** All eight are pure REST APIs; nothing requires a browser after key creation. None publishes a "personal server" or "automation" clause that would bite a single-tenant scheduler at 50 calls/day:

- **Groq** — Services Agreement: customer is "solely responsible for … authorizing an agentic AI Model Service … access and connection to any data, applications, and systems" and for "the actions and tasks performed by any agentic features"; no resale/lease of the account; no accessing "in a manner intended to avoid incurring Fees". Customer retains IP in inputs and outputs; Groq may not train on them "unless explicitly granted permission"; deletion within 30 days of termination [9]. Rate limits apply at the **organization** level, not per key [1].
- **Cerebras** — Terms prohibit "any robot, spider, scraper … or any other automated means to access the Service" *except through the API per the documentation*, prohibit disproportionate load "as determined by Cerebras", and forbid buying/selling/transferring API keys. Cerebras gets no right "to use Service Content for the purpose of training or fine-tuning models" [22].
- **Fireworks** — ToS (PDF v7.10.26, extracted 2026-09-24 in the verification pass [92]) §3.6 "Zero Data Retention": "We will not use your Content to train our own models or to improve the Service … we will not … (i) log your Content for human review; or (ii) retain your Content, beyond the time it takes to generate Output and deliver that Output to you"; carve-outs: safety-screening tools, and the commitment "does not apply to … the Response API and any training, fine-tuning, or agent features". Automated-access clause bans robots/scrapers only when they send "more request messages … than a human can reasonably produce … using a conventional on-line web browser" — API use per the docs is the intended path; also bans "unreasonable or disproportionately large load" and sharing API keys. **No financial/medical-data clause** (the only "financial" hit is the confidentiality section's "financial or legal advisors"). Data-handling doc agrees: "Fireworks does not log or store prompt or generation data for any open models, without explicit user opt-in" [31].
- **Together** — ToS bans exceeding "limits on the number and frequency of such calls", reverse-engineering, and building a competing product; user retains "all right, title, and interest in Your Content and Output". **Default setting retains prompts/outputs (no ZDR); Together's privacy policy states it does 'not use any data collected from you to train our models without your explicit opt-in and consent'. Enable Zero Data Retention under Settings > Profile (prospective only)** [44][45]. Together's ZDR doc [91] names the actual toggles and their defaults: (1) "Store prompts and model responses" — **on by default**, turning it off = ZDR (and auto-disables passthrough models); (2) "Training" — **off by default**, "a separate opt-in"; (3) "Passthrough models" — on by default, independent of ZDR. Org-level settings govern org API keys; the personal-profile toggle only covers personal-account traffic. The privacy page itself never states the defaults — a human should log in and read Settings > Profile before relying on this "retains by default" language. ToS also says "You will not use the Services to transmit or provide to the Company any financial or medical information of any nature or any sensitive personal data" — read literally this touches Atlas summaries (see §6).
- **DeepInfra** — ToS: "will not retain, store, or log any Customer Data … beyond the period strictly necessary to process and return the applicable request"; no training "except as necessary to provide the Services"; diagnostic retention up to 30 days only with written authorization. No agent restriction; "exceed or circumvent any usage limits" is the only relevant prohibition [52]. Data-privacy doc: prompts/outputs "not stored" on disk, processed in memory, small-sample debug logging reserved; Google/Anthropic resold models follow those vendors' policies [51].
- **SambaNova** — privacy policy covers marketing/applicant data only; inference retention "Not found — searched: sambanova.ai/privacy-policy, docs.sambanova.ai llms.txt index (no data-privacy page listed)" [61]; re-checked 2026-09-24: sambanova.ai/terms-of-service, sambanova.ai/legal/terms-of-service, sambanova.ai/security, docs.sambanova.ai/cloud/docs/get-started/data-privacy all 404, trust.sambanova.ai is JS-only — **SambaNova's inference data-retention position remains unread**, so the §3/§6 data-terms comparison is complete for five of six hosts (Fireworks closed above), not six. Status page lists a Japan region alongside US [62].
- **Ollama Cloud** — Terms: "Use automated means to access our services without permission" is prohibited (Section 4), but the API key + documented `ollama.com/v1` endpoint *is* the permission path; "We do not use your inputs or outputs to train AI models" (Section 5) [71]. Privacy: prompts/responses processed "transiently", metadata excludes content, US processing [70].
- **OpenRouter** — rate limits are governed globally; extra accounts/keys do not raise them; `:free` model variants show each provider's retention/training status, and there are separate paid/free training opt-out settings [72][73].

**Rate limits vs this lane (≈50 calls/day, ≤2 concurrent, ≤10k-token requests):**

| Host | Free / no-card tier | Paid tier | Fits the lane free? |
|---|---|---|---|
| Groq | Per model: `gpt-oss-120b`, `gpt-oss-20b`, `qwen3.8-27b` each **30 RPM / 1,000 RPD / 8,000 TPM / 200,000 TPD** [1]. Per-model max completion tokens: gpt-oss-120b/20b 65,536; qwen3.8-27b 16,384; minimax-m2.7 131,072 [2] | Developer plan: "higher limits", Batch + Flex; exact table not public (login-gated) [1][7] — but the page now says "the limits shown below are the base limits for the Developer plan", so the Developer table may simply be what a logged-in account sees; re-check with an account (unverified as of 2026-09-24) | **Yes for classification** (≈130k tok/day < 200k TPD); **8k TPM means a single 10k-token summary request is rejected** — keep summaries <7k tokens or split across `120b` and `20b` (separate buckets → 400k TPD) |
| Cerebras | Per model: **5 RPM / 30k uncached TPM / 90k total TPM / 1M TPH / 1M TPD**; 64k context, 32k max output; $5 signup credit [12][14][15][19] | Developer (≥$10 funding, "10× higher rate limits" per the marketing page [19]): `gpt-oss-120b` 1k RPM / 1M uncached TPM / **3M total TPM**; `qwen-3.8-27b` 300 RPM / 150k uncached TPM / **750k total TPM** ("temporarily increased from standard 450K"); no hourly/daily caps [12]. Note the "10×" is marketing copy: the actual table is 5→1,000 RPM (200×) and 30k→1M uncached TPM (33×) for gpt-oss-120b (unverified as of 2026-09-24) | **Yes, comfortably** (220k/day vs 1M TPD; 10k summaries under 30k TPM; 5 RPM ≥ 2 concurrent short jobs) |
| Fireworks | **10 RPM** with no payment method / no credits; $1 free credit [24][27] | 6,000 RPM fixed account cap; adaptive TPM ceilings for <400B models 64.8M total prompt TPM / **16.2M uncached prompt TPM** / 648k generated TPM (400B–1.6T: 43.2M / 10.8M / 432k; ≥1.6T: 21.6M / 5.4M / 216k) [27][28]; legacy self-serve postpaid accounts carry monthly spend caps by tier: **$50 (Tier 1, card on file) / $500 / $5,000 / $50,000** (Tiers 2–4 at $50 / $500 / $5,000 cumulative spend), unlimited via sales [27] | Technically yes at 10 RPM, but $1 of credit is ~4 days of the lane |
| Together | **None** — "does not offer free trials", $5 minimum purchase, fully prepaid [37] | Dynamic per-model limits, unpublished, grow with sustained use [36] | No free path; $5 lasts ~4 months of the lane |
| DeepInfra | No free credits found ("Not found — searched: deepinfra.com/pricing, docs.deepinfra.com/account/rate-limits") | 200 concurrent requests per model default; the page's own guidance is that this equals ~12,000 RPM at 1 s responses, ~1,200 RPM at 10 s, ~200 RPM at 60 s, and that "you may occasionally receive 429 errors when a model becomes very busy, even if you're under the limit" (auto-scaling kicks in; retry after a brief wait) [50] | No free path; cheapest metered (§4) |
| SambaNova | Production models except MiniMax-M2.7 (not in the Free-tier table; Developer-only) **20 RPM / 20 RPD / 200k TPD** [57]. Preview MiniMax-M3 (1M ctx) is on the supported-models page [58] but absent from the rate-limits page — its free/developer limits are unknown, not "20 RPM/20 RPD" (unverified as of 2026-09-24) | Developer: 60 RPM / 12,000 RPD (Llama 3.3 70B 240 RPM / 48,000 RPD), **20M tokens/day account cap** [57] | **No** — 20 requests/day is under half the lane |
| Ollama Cloud | Free: "starter usage credits included" **and** "includes access to starter models" — i.e. model-restricted, not just credit-restricted; 1 concurrent [63] | Pro $20 → $60 credits, 3 concurrent [63] | Starter credits unpublished; Pro covers it ~40× over (§4) |
| OpenRouter `:free` | **20 RPM / 50 RPD** (<$10 lifetime) or **20 RPM / 1,000 RPD** (≥$10 lifetime) [72] | pass-through + fee | **Yes after a one-time $10 top-up**; 50 RPD is below the lane |

**Security posture (what could be verified).** Groq DPA: 15-day subprocessor notice, US + other-country processing, 180-day max deletion after termination [10]. Cerebras: "We do not retain inputs and outputs associated with our … inference … Services"; US + other countries [21]. Fireworks: ZDR default for open models (and now contractual in ToS §3.6 [92]); regions in US (10), EU (Frankfurt, Iceland), APAC; the regions page says serverless region pinning requires contacting sales [31][32], **but** the serverless pricing page lists self-serve "US-only Serverless" model variants (e.g. DeepSeek V4.1 Flash (US) $0.45/$0.009/$1.80, Kimi K3 (US)) priced at 1.5× base from 2026-09-01 [25] — so US-pinned serverless exists without sales, partly contradicting [32]. Together: ZDR is a self-serve toggle, prospective only [44]. DeepInfra: ZDR in ToS; "specifically in the United States" [52][53]. SambaNova: US + Japan region [62]. SOC 2 / ISO status, all six hosts (checked 2026-09-24): **Cerebras — SOC 2 Type 2** report available on request, plus GDPR/CCPA statements, no ISO 27001/HIPAA shown (trust.cerebras.ai [93]); **Groq, Together, Fireworks, SambaNova** — trust-center pages (trust.groq.com, trust.together.ai, trust.fireworks.ai, trust.sambanova.ai) returned only a title (JS-rendered), status "Not found"; Fireworks' ToS refers to "requisite compliance or certifications" without naming any [92]; **DeepInfra** — no certification statement on docs.deepinfra.com (trust.deepinfra.com 403; only "private deployments for compliance" marketing), status "Not found". Treat SOC 2 as confirmed for Cerebras only. EU residency on a self-serve tier: none of the six offers it; OpenRouter EU in-region routing is enterprise-only [73].

---

## 4. Cost

### 4.1 List prices, $ per 1M tokens (input / output; cached input in parentheses)

| Model | Groq | Cerebras | Fireworks (Standard) | Together | DeepInfra | SambaNova | Ollama Cloud | OpenRouter cheapest endpoint |
|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 0.15 (0.075 cached, 50 % off) / 0.60 [2][94] | **0.35 / 0.75** (~3,000 tok/s; prompt caching listed as a capability but no cached-input price published) [14] | 0.15 (0.015) / 0.60 [25] | 0.15 / 0.60 [35] | **0.037 / 0.17** [49] | 0.22 / 0.59 [55] | 0.15 / 0.60 [88] | AkashML/CoreWeave 0.03 / 0.17 [74] |
| gpt-oss-20b | 0.075 (0.0375 cached) / 0.30 [2][94] | — | not listed [25] | — | — | — | listed, price not shown [66] | — |
| Qwen3.8-27B | 0.80 / 4.00 (preview) [2] | 0.99 / 1.49 (~1,850 tok/s) [15] | listed, price n/f [26] | — | 0.15 / 1.875 (bf16) [75] | — | — | Reka 0.094 / 4.40 [75] |
| Qwen3.8 Max / 2.4T-A95B | — | — | 2.00 (0.25) / 6.00 [25] | 2.00 (0.25) / 6.00 [35] | 2.00 (0.20) / 6.00 [48] | — | — | — |
| Qwen3.8 Flash | — | — | — | 0.09 / 0.28 [35] | — | — | — | — |
| GLM-5.3 | — | — | 1.40 / 4.40 [26] | 1.40 (0.26) / 4.40 [35] | **0.563 (0.125) / 2.50** [48] | — | listed [66] | — |
| GLM-5.3-Flash | — | — | 0.15 (0.03) / 0.50 [25] | 0.15 (0.03) / 0.50 [35] | **0.075 (0.015) / 0.25** [48] | — | 0.15 (0.03) / 0.50 [67] | InferenceNet 0.045 / 0.14 [76] |
| DeepSeek V4 Flash 0731 | — | — | 0.22 (0.007) / 0.66 [25] | 0.14 (0.03) / 0.28 [35] | 0.06 / 0.18 [47] | — | 0.22 / 0.66 off-peak, 0.44 / 1.32 peak [68] | — |
| DeepSeek V4.1 Flash | — | — | 0.30 (0.006) / 1.20 per docs.fireworks.ai/serverless/pricing [25] (the fireworks.ai/models card shows 0.22 / 0.66 — the two Fireworks pages disagree); a "(US)" region variant is 0.45 (0.009) / 1.80 | 0.30 (0.006) / 1.20 [35] | 0.14 (0.004) / 0.42 ("promotional pricing, 30% off already applied", fp8; will change (unverified as of 2026-09-24)) [47] | — | listed [66] | — |
| DeepSeek V4 Pro (0813) | — | — | 1.32 / 3.96 [26] | 1.32 (0.13) / 3.96 [35] | 1.30 (0.10) / 2.60 [48] | — | 1.32 / 3.96 [88] | — |
| Kimi K3 | — | — | 3.00 / 15.00 [25] | 3.00 (0.30) / 15.00 [35] | 2.85 (0.285) / 14.25 [48] | — | 3.00 (0.30) / 15.00 [69] | — |
| MiMo-V2.6-Flash / Pro | — | — | not listed | not listed | 0.14 / 0.28 ; 0.435 (0.004) / 0.87 [48] | — | not listed [66] | listed on `openrouter.ai/xiaomi`, price not shown [89] |
| Muse Glimmer 30B (Meta) | — | — | 0.35 (0.04) / 1.50 [25][33] | listed, no JSON/tools [39] | — | — | — | — |
| Llama 3.3 70B | enterprise-only [2][3] | — | listed [26] | 1.04 / 1.04 [35] | — | 0.60 / 1.20 [55] | — | — |
| MiniMax M3 / M2.7 | M2.7 enterprise [2] | — | — | M3 0.30 / 1.20 [35] | — | M3 0.60 / 2.40; M2.7 0.60 (0.06) / 2.40 [55] | listed [66] | — |

Batch / service tiers: Groq Batch **50 % off**, 24h–7d window, does not consume standard per-model limits, does not stack with cache discount, paid plan only; Flex = same price, 10× limits, fails fast with `498 capacity_exceeded` [6][7]. Fireworks batch **50 % off** plus cache; expiry 12/24/48/72h; Priority tier is ~1.2–1.25× list on the checked rows (gpt-oss-120b $0.18/$0.72; GLM-5.3-Flash $0.1875/$0.625); the page states no general multiplier [25][30]. Together batch **up to 50 % off** on selected models, 24h best-effort, 50k requests/batch [42]. DeepInfra Flex tier **0.8×**, Priority 1.5× [47]; bulk API docs "Not found — searched: docs.deepinfra.com/inference/bulk, deepinfra.com/docs/bulk". Cerebras/SambaNova: no batch found. Ollama Cloud: no batch [65].

Prompt caching on the two free hosts: **Groq** caches automatically on gpt-oss-120b/20b/safeguard-20b with a **50 % discount on cached input tokens**, minimum cacheable prefix 128–1,024 tokens depending on model, no code change and no plan restriction; the discount does not stack with batch (batch tokens are all billed at the 50 % batch rate regardless of cache status) [6][94]. **Cerebras** lists "Prompt Caching" as a gpt-oss-120b capability [14] and its rate-limit page says "cached tokens don't count toward your uncached TPM limit" [12], but publishes **no cached-input price** — on Cerebras the cache is a rate-limit benefit (30k uncached vs 90k total TPM on Free), not a billing one, as far as the fetched pages show.

### 4.2 Plans and free tiers

| | Free | Paid entry | Notes |
|---|---|---|---|
| Groq | Free plan, no card; limits in §3 [1] | Developer plan (pay-as-you-go; unlocks Batch/Flex) [1] | Preview models (Qwen3.8-27B, MiniMax) "may discontinue with limited notice"; Llama 3.x moved to enterprise-only 2026-08-16; `groq/compound` shut down 2026-09-21 [3] |
| Cerebras | Free Trial + **$5 credit** [19] | Developer: **$10 minimum** funding, 10× limits [19] | Cerebras Code Pro $50 (24M tok/day) / Max $200 (120M tok/day) — both **"Sold out"**, model still GLM-4.7 [20] — point-in-time state; Cerebras says new plans will be announced via X/newsletter (unverified as of 2026-09-24) |
| Fireworks | $1 credit, 10 RPM [24][27] | postpaid; spend tiers $50 / $500 / $5,000 raise TPM ceilings [27] | |
| Together | none [37] | **$5 minimum**, prepaid, auto-recharge [37] | |
| DeepInfra | none found | pay-as-you-go, no minimum stated [47] | |
| SambaNova | Free: production models, 20 RPD [56][57] | Developer PAYG; Enterprise subscription [56] | |
| Ollama Cloud | Free: starter credits, 1 concurrent [63] | **Pro $20/mo ($200/yr) → $60 credits, 3 concurrent**; Max $100 → $300, 10 concurrent; Team $500 → $1,000 shared, 10 concurrent (early access); credits reset monthly, no rollover [63] | |
| OpenRouter | `:free` variants (50 or 1,000 RPD) [72] | pass-through + 5.5 % fee [88] | 22 `:free` variants at the time of the runtimes doc [88]; today's free-filter page shows only `stealth/space-bunny-alpha` as a $0 text LLM [77] — the free list churns weekly, so any `:free` count here is already stale (unverified as of 2026-09-24) |

### 4.3 Monthly cost for this server's load

Assumptions restated: 1,500 jobs/month = 6.6M input + 0.6M output tokens; no prompt-cache credit assumed (the lane's prompts are short and varied; if a shared system prompt ≥128–1,024 tokens is used, Groq would bill that prefix at 50 % and Cerebras would exclude it from the uncached-TPM bucket — see §4.1, both left out of the figures below); "Agent-shape" column = 1,500 × (150k in + 15k out) = 225M in + 22.5M out, shown only to expose the cliff.

| Lane option | Model | $/mo classification+summary lane | $/mo if the lane were agent-shaped | Free-tier verdict |
|---|---|---|---|---|
| Cerebras Free | gpt-oss-120b | **$0** (1M TPD ≫ 220k/day) | $0 until 1M TPD, i.e. ≤6 agent jobs/day | Best free fit; $5 credit as buffer [12][14] |
| Cerebras paid | gpt-oss-120b @ 0.35/0.75 | $2.76 | $95.6 | fastest option (~3,000 tok/s) [14] |
| Groq Free | gpt-oss-120b (+20b as second bucket) | **$0** for classification; summaries must fit 8k TPM | $0 impossible (150k in > 8k TPM) | Second free fit [1] |
| Groq paid | gpt-oss-120b @ 0.15/0.60 | $1.35 | $47.25 | Batch halves this [6] |
| Groq paid | gpt-oss-20b @ 0.075/0.30 | $0.68 | $23.6 | 1,000 tok/s [2] |
| DeepInfra | gpt-oss-120b @ 0.037/0.17 | **$0.35** | $12.15 | cheapest metered [49] |
| DeepInfra | GLM-5.3-Flash @ 0.075/0.25 | $0.65 | $22.5 | best $/intelligence per matrix [48][88] |
| DeepInfra | DeepSeek V4 Flash @ 0.06/0.18 | $0.50 | $17.6 | [47] |
| DeepInfra | MiMo-V2.6-Flash @ 0.14/0.28 | $1.09 | $37.8 | [48] |
| Fireworks | GLM-5.3-Flash @ 0.15/0.50 | $1.29 | $45 | ZDR default; $1 credit ≈ 3 weeks [25][31] |
| Fireworks | gpt-oss-120b @ 0.15/0.60 | $1.35 | $47.25 | [25] |
| Together | DeepSeek V4 Flash 0731 @ 0.14/0.28 | $1.09 | $37.8 | $5 min buy ≈ 4.5 months [35][37] |
| Together | Qwen3.8 Flash @ 0.09/0.28 | $0.76 | $26.6 | no JSON mode/tools on this model [39] |
| SambaNova Developer | gpt-oss-120b @ 0.22/0.59 | $1.81 | $62.8 | 20M tok/day cap fine [55][57] |
| Ollama Cloud Pro | GLM-5.3-Flash @ 0.15/0.50 | $1.29 of the $60 credit (**$20/mo sub**) | $45 of $60 credit | $58.7 of credit left for other lanes each month [63][67] |
| OpenRouter `:free` | whatever is free that week | $0 after one-time $10 top-up | not viable (1,000 RPD ok, but free hosts may train/retain) | unstable catalogue [72][77] |

Reading: the metered cost of this lane is **under $3/month on every host** — the decision is not price, it is (a) whether $0 is achievable without a card and (b) data terms, JSON reliability and catalogue breadth. Only if the open-weight lane grows to agent-shaped jobs does price dispersion matter (DeepInfra $12 vs Cerebras $96 vs Groq $47).

---

## 5. Strengths & weaknesses per reviews

**Independent speed/price (ArtificialAnalysis, gpt-oss-120b, fetched 2026-09-24 [78]):** *Columns used: "Median Tokens/s" (output speed), "Median First Chunk" (TTFT, s), "Total Response" (seconds to output 500 tokens — end-to-end, not TTFT), "Cost per Task" (USD for AA's standard workload — not a blended $/1M price; AA's separate "Blended Price" is a 7:2:1 cache-hit/input/output $/1M figure), and "Endpoint Accuracy Index" (how much of the model's accuracy the endpoint preserves): SambaNova 98 %, DeepInfra 97 %, Cerebras 87 %, Groq 86 %, Together 77 % — for a classification lane the accuracy column argues for SambaNova/DeepInfra over the two fast hosts, and against Together.* Cerebras 1,744 tok/s (TTFT 0.50 s, 1.94 s end-to-end; AA's $0.23 is its 'Cost per Task' column, not a blended $/1M price, so it does not conflict with the $0.35/$0.75 model page [14]); SambaNova 709 tok/s (1.07 s TTFT, 4.59 s end-to-end, $0.15/task); Groq 473 tok/s (0.74 s TTFT, 6.02 s end-to-end, $0.08/task); DeepInfra Turbo 227 tok/s (0.71 s TTFT, $0.11/task), DeepInfra standard 36 tok/s (0.82 s TTFT, $0.03/task); Together 84 tok/s (0.53 s TTFT, $0.11/task). Fireworks is not in the gpt-oss-120b AA table. For GLM-5.3 [80]: Together 267 tok/s / 0.63 s TTFT / $2.58 blended; Fireworks 225 tok/s / 0.88 s / $2.15; DeepInfra 101 tok/s / 1.11 s / $0.72. For Qwen3.8-27B [79]: DeepInfra 34 tok/s at $0.41 blended; Groq/Cerebras not tracked by AA for that model, but vendor pages claim 450 tok/s (Groq) [2] and ~1,850 tok/s (Cerebras) [15].

**Status-page record, Jun–Sep 2026 (vendor pages [11][23][34][46][54][62]):** Groq: 100 % on every component, no incidents in 90 days — but the component list still includes retired items (groq/compound, llama-3.x, kimi-k2, qwen3-32b) no longer served to Free/Developer users, so the claim is true but partly vacuous for the current catalogue (unverified as of 2026-09-24). Cerebras: all operational, no incidents in the visible window, 90-day % not displayed. Fireworks: 28 serverless components, most at 100 %, GLM 5.2 99.86 %, Kimi K3 99.70 %; **an active "Qwen 3.8 Max impacted performance" incident was open at fetch time** — and again at the 2026-09-24 verification check ("Service Degradation for Qwen 3.8 Max", investigating), i.e. recurring, not one-off, while the page still shows GPT-OSS 120B and Qwen 3.8 Max at 100 % 90-day (unverified as of 2026-09-24). Together: the weakest — gpt-oss-120B 99.477 % (2 h outage 09-07, plus further incidents 09-22 12 min and 09-23 36 min), Kimi K3 additional outages 09-02 59 min, 09-06 33 min, 09-08 53 min, 09-10 32 min, 09-13 36 min (September is worse than the original paragraph implied (unverified as of 2026-09-24)), Qwen3.5 9B 99.370 % (2 h+ 09-13), Kimi K3 98.881 % (7 h+ on 08-21), Qwen3.8-2.4T 98.670 % (5 h+ 08-12, 3 h+ 09-09). DeepInfra: API 100 %, but gemma-4-31B-it-turbo had 8 h and 6 h outages 07-25/26 and gpt-oss-120b a 72-min partial on 07-24; four deprecations from 09-29 (MiMo-V2.5→V2.6, Kimi-K2.7-Code→K3, DeepSeek-V3-0324→V4.1-Flash among them — landing 5 days after this doc's date (unverified as of 2026-09-24)). SambaNova: all operational, US + Japan. OpenRouter's 30-minute uptime column at fetch [74][76]: Groq 99.95 %, Cerebras 100 %, DeepInfra 98.1 %, Fireworks 99.9 %, SambaNova 93.5 %, **Together 72.5 % on gpt-oss-120b and 94.0 % on GLM-5.3-Flash** — consistent with its status history.

**Community sentiment (HN via Algolia API, quoted with author/date [81]–[87]):**
- Groq/Cerebras free tiers "very generous" (el_isma, 2024-12-15); Cerebras "latency of their model inference is insane" (alfalfasprout, 2026-03). Against: Groq "latency wasn't always consistent and I saw some very strange responses on a few calls" attributed to quantization (ilaksh, 2026-03-03); Cerebras "provides high-speed inference at high cost. It's never going to be the cheapest" (wmf, 2026-08); Cerebras Code catalogue "somewhat dated GLM 4.7" and 24M tok/day exhausted quickly on large codebases (KronisLV, 2026-05); WSE-3 44 GB/chip explains the tiny catalogue (jychang, 2026-02).
- DeepInfra: "so cheap" for DeepSeek V4 Flash (joshheitzman, 2026-09-21); "US based and has ZDR" (johnnyApplePRNG, 2026-08-18); "excellent terms of service" (matheusmoreira, 2026-08-28). Against: cache-hit pricing "almost 6× DeepSeek's" (Tiberium, 2026-08-13); MoE experts served fp4 (wgd, 2026-08-08); listed among "providers that always suck" (Semaphor, 2026-09-11); results "much too noisy" for research consistency (ndr_, 2026-09-12). OpenRouter's endpoint data confirms DeepInfra serves GLM-5.3-Flash at fp4 but gpt-oss-120b and Qwen3.8-27B at bf16 [74][75][76].
- Fireworks: "monthly bill is between $10 and $40 and much faster than any reasonable home rig" (mark_l_watson, 2026-08); "Fireworks has zero data retention by default" and preferred over OpenRouter for enterprise (jmtulloss, 2026-09). Against: errors on Qwen3.8 "before reaching 10 % through context window" (0xc133, 2026-08). Together: praised only generically as a reliable Anthropic alternative alongside Fireworks (dkersten, 2026-08); no substantive Together-specific commentary found.
- SambaNova: "Vertex and SambaNova do pretty good" on open weights but behind Groq (petesergeant, 2025-10-12); "sambanova-intel is akin to a firesale" (chermanowicz, 2025-12-25).
- Ollama Cloud: "using GLM-5.3-Flash on Ollama Cloud's $20/mo plan… I hit a daily or weekly limit MAYBE once a month" (alexpotato, 2026-09-24); "Prompt or response data is never logged or trained on" (hbcondo714, 2026-07-12); "Ollama cloud service is still alive :D" during a multi-vendor outage (authentictimers, 2026-09-03).

**Structural weaknesses to weigh:** Groq's catalogue is now essentially gpt-oss + one preview Qwen; it moved Llama to enterprise-only and retires preview models with "limited notice" [3]. Cerebras has two public models and its paid coding plans are sold out [13][20]. Together retains prompts/outputs by default unless ZDR is toggled (training is explicit opt-in per its privacy policy) and has the worst uptime record [44][46]. DeepInfra has no free tier and mixed precision. SambaNova's catalogue lags a full generation (DeepSeek V3.x, no Qwen3.8/GLM-5.3/Kimi K3) [58]. None supports Anthropic-format requests.

---

## 6. Finance / trading relevance

Nothing host-specific: none of the six ships market data, finance tools, or a finance-tuned model, and none has a finance-specific AUP clause beyond generic advice disclaimers. Two terms matter for Atlas:

- **Together's ToS says "You will not use the Services to transmit or provide to the Company any financial or medical information of any nature or any sensitive personal data"** [45]. Read literally this excludes routing Atlas research/paper-ledger summaries through Together even with ZDR on. Treat Together as unusable for the Atlas lane until a human reads the clause in full.
- **Every free tier is a data-terms question, not a capability one.** Cerebras (no retention of inputs/outputs [21]), Groq (no training, processor-only DPA [9][10]), DeepInfra (ZDR in ToS [52]), Fireworks (ZDR default [31]) and Ollama Cloud (no training, transient processing [70][71]) are all clean enough for paper-trading research text. OpenRouter `:free` endpoints inherit the *upstream* host's terms, several of which retain/train (e.g. "Space Bunny Alpha… prompts and completions may be retained by the provider" [77]) — do not send Atlas content to `:free` variants.

For the research loops themselves the relevant fact is speed: at ~1,700–3,000 tok/s (Cerebras) or ~450–1,000 tok/s (Groq; its own models page lists gpt-oss-120b at ~500 tok/s and gpt-oss-20b at 1,000 tok/s [2], AA measured 473 [78]) a 30-file summarization pass finishes in seconds, which makes a "cheap first pass, Claude second pass" pattern practical inside the existing 2-concurrent job budget.

---

## 7. Integration recipe for our server

**Recommended shape:** one thin `openweight_lane.py` provider table keyed by host, all OpenAI-compatible, with Cerebras Free as primary, Groq Free as automatic fallback on 429/5xx, and DeepInfra as the paid overflow (card on file, ~$1/month). Keep Ollama Cloud Pro as the Anthropic-format lane for anything the Claude Agent SDK must drive. Do not put OpenRouter `:free` in the Atlas path.

```python
# src/runner/openweight_lane.py  (sketch; python 3.12, openai>=1.x)
import os, time, json
from openai import OpenAI, RateLimitError, APIStatusError

HOSTS = [  # ordered fallback chain
    dict(name="cerebras", base_url="https://api.cerebras.ai/v1",
         key=os.environ["CEREBRAS_API_KEY"], model="gpt-oss-120b",
         max_input_tokens=60_000),                        # free tier ctx 65k [14]
    dict(name="groq", base_url="https://api.groq.com/openai/v1",
         key=os.environ["GROQ_API_KEY"], model="openai/gpt-oss-120b",
         max_input_tokens=7_000),                         # free tier 8k TPM [1]
    dict(name="deepinfra", base_url="https://api.deepinfra.com/v1/openai",
         key=os.environ["DEEPINFRA_API_KEY"], model="openai/gpt-oss-120b",
         max_input_tokens=120_000),                       # paid overflow [49]
]

ROUTE_SCHEMA = {  # strict json_schema works on gpt-oss-120b at Cerebras+Groq [4][16]
    "name": "route", "strict": True,
    "schema": {"type": "object", "additionalProperties": False,
               "required": ["lane", "confidence", "summary"],
               "properties": {"lane": {"type": "string", "enum": ["research", "code", "ops", "finance", "chat"]},
                              "confidence": {"type": "number"},
                              "summary": {"type": "string"}}}}

def classify(text: str, est_tokens: int) -> dict:
    last = None
    for h in HOSTS:
        if est_tokens > h["max_input_tokens"]:
            continue
        client = OpenAI(base_url=h["base_url"], api_key=h["key"], timeout=60)
        try:
            r = client.chat.completions.create(
                model=h["model"],
                messages=[{"role": "system", "content": "Classify the job and reply as JSON."},
                          {"role": "user", "content": text}],
                response_format={"type": "json_schema", "json_schema": ROUTE_SCHEMA},
                extra_body={"reasoning_effort": "low"},   # gpt-oss knob; default medium [14]
                max_tokens=400, temperature=0)
            out = json.loads(r.choices[0].message.content)
            out["_host"], out["_usage"] = h["name"], r.usage.model_dump()
            return out                                     # write _usage to the cost table
        except (RateLimitError, APIStatusError) as e:
            last = e; time.sleep(1.5); continue           # 429 → next host, no retry storm
    raise RuntimeError(f"all open-weight hosts failed: {last}")
```

Config/ops notes:
- Keys in the launchd env file only (`CEREBRAS_API_KEY`, `GROQ_API_KEY`, `DEEPINFRA_API_KEY`); never `ANTHROPIC_API_KEY` (policy). Groq limits are org-level, so one key per environment is enough [1].
- Record `usage.prompt_tokens/completion_tokens` and `x-ratelimit-remaining-tokens` (Groq) per call into the existing cost-event table so the dashboard shows the daily free-tier burn against 1M (Cerebras) / 200k (Groq).
- Smoke test: `curl https://api.cerebras.ai/v1/chat/completions -H "Authorization: Bearer $CEREBRAS_API_KEY" -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"ping"}],"max_tokens":5}'`; expect `429` after the 5th call within a minute on Free [12].
- For the Claude-Code-driven path: `ANTHROPIC_BASE_URL=https://ollama.com ANTHROPIC_AUTH_TOKEN=$OLLAMA_API_KEY claude -p ... --model glm-5.3-flash` per [65] (verify exact model naming via `/api/tags`).

Gotchas:
1. **Groq free 8k TPM effectively caps single-request size**: the rate-limits page documents only 429 on limit exceedance and does not state per-request rejection behaviour — size-gate before sending and confirm empirically [1] (unverified on the cited page).
2. **Cerebras free context is 64–65k, max output 32k; reasoning is on by default at `high` for Qwen3.8-27B** — set `reasoning_effort: "none"` for classification or you pay latency and TPM for thinking tokens [15].
3. **Do not combine `tools` and `response_format`** on Cerebras unless the model page says so; Groq: structured outputs exclude streaming and tool use [4][16].
4. **Strict schemas need `additionalProperties: false` everywhere and all fields `required`** (Groq, Cerebras); Cerebras caps schema text at 5,000 chars / 10 levels / 500 properties; `pattern`, `format`, `oneOf`/`allOf`/`not` and `minItems`/`maxItems` are unsupported in strict mode on all Cerebras models; Qwen3.8-27B strict tool schemas additionally reject `minLength`/`maxLength` [4][16][17].
5. **Fireworks Responses API stores conversations 30 days by default** — pass `store=False`, or use chat completions [31].
6. **Together retains prompts by default (training is opt-in)** — flip ZDR under Settings > Profile before the first call, and read the "financial or medical information" clause [44][45].
7. **Groq preview models vanish** (`qwen3.6-27b` → `qwen3.8-27b` 2026-09-14; compound shut down 2026-09-21) — pin to `openai/gpt-oss-120b` which is production-tier [3].
8. **DeepInfra precision varies per model** (fp4 GLM-5.3-Flash, bf16 gpt-oss/Qwen) — for a labeling lane it is fine; do not use it as a tie-break reviewer where determinism matters [74][76][84].
9. Cerebras free limits are **per model**, so `qwen-3.8-27b` is a second 1M-token bucket; Groq likewise (`gpt-oss-20b`) [1][12].
10. OpenRouter free-model daily counter is readable from `GET /api/v1/key` (`free_model_daily_requests`) — the only host here that exposes remaining free budget as an API field [72].

---

## 8. Verdict

1. **Cerebras Free is the recommended primary for the classification/routing/summarization lane**: 1M tokens/day + 5 RPM covers 50 jobs/day 4× over, strict `json_schema` on `gpt-oss-120b`, no retention of inputs/outputs, ~3,000 tok/s, $5 credit as a buffer, and clean automation terms.
2. **Groq Free is the automatic fallback** (independent 200k-token/day buckets per model, 100 % 90-day uptime, no training), with the caveat that 8k TPM caps request size.
3. **DeepInfra is the paid overflow / catalogue lane** (~$0.35–$1/month for this load, GLM-5.3-Flash + DeepSeek V4 Flash + MiMo, ZDR in the ToS, no free tier); Fireworks is the better-uptime alternative if fp4 or noise ever bites.
4. **Ollama Cloud Pro stays the subscription-shaped lane** for anything driven through the Anthropic API surface; OpenRouter `:free` is fine for throwaway experiments only, never Atlas content.
5. **Skip Together (retains by default unless ZDR is toggled, worst uptime, "financial or medical information" clause, no free tier) and SambaNova (20 req/day free, generation-old catalogue)**.

Fit scores (1–10, this server's use):

| Axis | Groq | Cerebras | Fireworks | Together | DeepInfra | SambaNova | Ollama Cloud Pro | OpenRouter |
|---|---|---|---|---|---|---|---|---|
| Research | 5 (2 chat models) | 5 (2 chat models) | 7 | 6 | 8 (widest catalogue) | 3 | 7 | 8 |
| Coding / agentic | 5 (gpt-oss + tools; no Kimi/GLM) | 5 | 8 (Kimi K3, GLM-5.3, Muse; tool+JSON) | 7 | 7 | 3 | 7 (Anthropic endpoint, but no structured outputs [88]) | 8 |
| Cost efficiency | 9 (free covers the lane) | 9 (free covers the lane) | 6 | 5 | 9 (cheapest metered) | 4 | 8 ($60 credits/$20) | 7 |
| Automation friendliness | 8 (headers, org limits, batch/flex; small TPM) | 8 (clean terms, per-model buckets) | 7 (ZDR default, adaptive limits, 30-day Responses store) | 4 (unpublished dynamic limits, opt-in ZDR) | 7 (200 concurrent, ZDR ToS) | 4 (20 RPD free) | 7 (concurrency 3, no batch) | 7 (global limits, key-readable free budget) |
| Trading research | 6 (fast summaries, clean data terms; no data tools) | 6 | 6 | n/a — ToS bars transmitting "any financial or medical information of any nature" [45] | 6 | 4 | 6 | 3 (`:free` upstreams may retain) |

---

## 9. Sources

All accessed 2026-09-24.

1. https://console.groq.com/docs/rate-limits — free-plan per-model RPM/RPD/TPM/TPD, org-level limits, headers
2. https://console.groq.com/docs/models — model IDs, speeds, prices, enterprise-only Llama
3. https://console.groq.com/docs/deprecations — Llama→gpt-oss 2026-08-16, qwen3.6→3.8 2026-09-14, compound shutdown 2026-09-21
4. https://console.groq.com/docs/structured-outputs — strict json_schema models, no streaming/tools
5. https://console.groq.com/docs/tool-use — tool models, parallel calls, built-in browser/code tools
6. https://console.groq.com/docs/batch — 50 % discount, 24h–7d, separate limits
7. https://console.groq.com/docs/flex-processing — paid-only, 10× limits, 498 capacity_exceeded
8. https://console.groq.com/docs/responses-api — Responses API beta, base URL
9. https://console.groq.com/docs/legal/services-agreement — agentic-use responsibility, no training, IP in outputs
10. https://console.groq.com/docs/legal/customer-data-processing-addendum — retention, subprocessors, US processing
11. https://groqstatus.com — 100 % 90-day uptime, no incidents
12. https://inference-docs.cerebras.ai/support/rate-limits — Free 5 RPM / 30k / 90k TPM / 1M TPD; Developer limits
13. https://inference-docs.cerebras.ai/models/overview — public models, speeds, free/paid context
14. https://inference-docs.cerebras.ai/models/openai-oss — gpt-oss-120b $0.35/$0.75, ~3,000 tok/s, features, free-tier notes
15. https://inference-docs.cerebras.ai/models/qwen-3.8-27b — Qwen3.8-27B $0.99/$1.49, ~1,850 tok/s, reasoning default
16. https://inference-docs.cerebras.ai/capabilities/structured-outputs — strict mode, model list, schema limits
17. https://inference-docs.cerebras.ai/capabilities/tool-use — tool models, parallel, strict tools
18. https://inference-docs.cerebras.ai/quickstart — base URL, SDKs, auth
19. https://www.cerebras.ai/inference — $5 free credit, $10 Developer minimum, 10× limits
20. https://www.cerebras.ai/code — Code Pro $50 / Max $200, 24M/120M tok/day, GLM-4.7, sold out
21. https://www.cerebras.ai/privacy-policy — no retention of inference inputs/outputs; US + other countries
22. https://www.cerebras.ai/terms-of-service — automated-access clause, no training right, API-key transfer ban
23. https://status.cerebras.ai — all operational, no incidents in window
24. https://fireworks.ai/pricing — $1 free credit, model list, embeddings prices
25. https://docs.fireworks.ai/serverless/pricing — per-model Standard/Priority prices
26. https://fireworks.ai/models — serverless catalogue with prices
27. https://docs.fireworks.ai/guides/quotas_usage/rate-limits — 10 RPM no-card, 6,000 RPM cap, spend tiers
28. https://docs.fireworks.ai/serverless/rate-limits — adaptive TPM ceilings by model size
29. https://docs.fireworks.ai/structured-responses/structured-response-formatting — json_schema 2020-12, grammar mode
30. https://docs.fireworks.ai/guides/batch-inference — 50 % off, expiry windows
31. https://docs.fireworks.ai/guides/security_compliance/data_handling — ZDR default, Responses 30-day store
32. https://docs.fireworks.ai/deployments/regions — US/EU/APAC regions, no serverless residency guarantee
33. https://fireworks.ai/models/fireworks/muse-glimmer-30b — Meta, Apache-2.0, $0.35/$0.04/$1.50
34. https://status.fireworks.ai — component uptimes, active Qwen 3.8 Max incident
35. https://www.together.ai/pricing — per-model prices incl. cached
36. https://docs.together.ai/docs/rate-limits — dynamic, unpublished limits
37. https://docs.together.ai/docs/billing — no free trial, $5 minimum, prepaid
38. https://docs.together.ai/docs/quickstart — base URL, SDK names
39. https://docs.together.ai/docs/serverless-models — model IDs, JSON/function support
40. https://docs.together.ai/docs/json-mode — response_format, regex mode
41. https://docs.together.ai/docs/function-calling — parallel calls
42. https://docs.together.ai/docs/batch-inference — up to 50 % off, 24h, limits
43. https://docs.together.ai/docs/openai-api-compatibility — supported endpoints; no Responses/Anthropic API
44. https://www.together.ai/privacy — ZDR toggle, opt-in training
45. https://www.together.ai/terms-of-service — rate-limit clause, default training, "financial data" clause
46. https://status.together.ai — per-model uptimes and outages
47. https://deepinfra.com/pricing — per-model prices, tiers, 200 concurrent
48. https://deepinfra.com/models/text-generation — Qwen3.8/GLM-5.3/Kimi K3/MiMo/DeepSeek prices
49. https://deepinfra.com/openai/gpt-oss-120b — $0.037/$0.17, bf16, tools/JSON
50. https://docs.deepinfra.com/account/rate-limits — 200 concurrent per model
51. https://docs.deepinfra.com/account/data-privacy — in-memory processing, no training, debug sampling
52. https://deepinfra.com/terms — ZDR commitment, no training, usage-limit clause
53. https://deepinfra.com/privacy — US processing
54. https://status.deepinfra.com — API 100 %, model incidents, deprecations 09-29
55. https://cloud.sambanova.ai/pricing — per-model prices
56. https://cloud.sambanova.ai/plans — Free / Developer / Enterprise
57. https://docs.sambanova.ai/docs/en/models/rate-limits.md — Free 20 RPM/20 RPD/200k TPD; Developer 60 RPM/12k RPD; 20M tok/day
58. https://docs.sambanova.ai/cloud/docs/get-started/supported-models — production/preview models
59. https://docs.sambanova.ai/docs/en/features/function-calling.md — tool models, JSON mode/schema
60. https://docs.sambanova.ai/docs/en/features/openai-compatibility — supported params
61. https://sambanova.ai/privacy-policy — no inference-retention terms found
62. https://status.sambanova.ai — all operational, Japan region
63. https://ollama.com/pricing — Free/Pro $20→$60/Max $100→$300/Team; concurrency; no rollover
64. https://docs.ollama.com/cloud — API key, endpoints, no training
65. https://docs.ollama.com/api/anthropic-compatibility — /v1/messages, Claude Code env vars, limitations
66. https://ollama.com/search?c=cloud — cloud model catalogue
67. https://ollama.com/library/glm-5.3-flash — $0.15/$0.03/$0.50, 1M ctx
68. https://ollama.com/library/deepseek-v4-flash — peak/off-peak prices
69. https://ollama.com/library/kimi-k3 — $3/$0.30/$15
70. https://ollama.com/privacy — transient processing, no training, US
71. https://ollama.com/terms — automated-access clause, no training
72. https://openrouter.ai/docs/api-reference/limits — 20 RPM; 50 vs 1,000 RPD; key endpoint field
73. https://openrouter.ai/docs/features/privacy-and-logging — provider data-policy filtering, EU routing enterprise-only
74. https://openrouter.ai/api/v1/models/openai/gpt-oss-120b/endpoints — per-provider price/quant/uptime
75. https://openrouter.ai/api/v1/models/qwen/qwen3.8-27b/endpoints — per-provider price/quant/uptime
76. https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints — per-provider price/quant/uptime
77. https://openrouter.ai/models?fmt=table&max_price=0&order=top-weekly — current $0 text models
78. https://artificialanalysis.ai/models/gpt-oss-120b/providers — speed/TTFT/blended price by provider
79. https://artificialanalysis.ai/models/qwen3-8-27b/providers — speed/price by provider
80. https://artificialanalysis.ai/models/glm-5-3/providers — Fireworks/Together/DeepInfra speed and price
81. https://hn.algolia.com/api/v1/search?query=groq%20cerebras%20free%20tier&tags=comment — sentiment
82. https://hn.algolia.com/api/v1/search?query=groq%20rate%20limit&tags=comment&numericFilters=created_at_i%3E1767225600 — 2026 Groq sentiment
83. https://hn.algolia.com/api/v1/search?query=cerebras%20inference&tags=comment&numericFilters=created_at_i%3E1767225600 — 2026 Cerebras sentiment
84. https://hn.algolia.com/api/v1/search?query=deepinfra&tags=comment&numericFilters=created_at_i%3E1751328000 — DeepInfra sentiment
85. https://hn.algolia.com/api/v1/search?query=fireworks.ai&tags=comment&numericFilters=created_at_i%3E1751328000 — Fireworks/Together sentiment
86. https://hn.algolia.com/api/v1/search?query=sambanova&tags=comment&numericFilters=created_at_i%3E1751328000 — SambaNova sentiment
87. https://hn.algolia.com/api/v1/search?query=ollama%20cloud&tags=comment&numericFilters=created_at_i%3E1767225600 — Ollama Cloud sentiment
88. In-repo: `docs/research/llm-landscape-2026-09/00-comparison-matrix.md` — Ollama Cloud rows (no structured outputs on Cloud, 19 models, `ollama launch claude`), OpenRouter 22 `:free` variants and 5.5 % fee, AA v4.3.2 model rankings
89. https://openrouter.ai/xiaomi — MiMo model IDs on OpenRouter (no prices rendered)
90. https://groq.com/privacy-policy — consumer policy excludes GroqCloud customer data (see DPA)
91. https://docs.together.ai/docs/zero-data-retention — the three privacy toggles (store prompts ON by default; training OFF/opt-in; passthrough ON) and org-vs-personal scope (added 2026-09-24 verification)
92. https://cdn.sanity.io/files/pv37i0yn/production/60909f1a2f0cae74deb6ba7fc0f6eda8ab3bac4b.pdf — Fireworks Terms of Service PDF (v7.10.26), text-extracted 2026-09-24: §3.6 ZDR, automated-access clause, no financial-data clause
93. https://trust.cerebras.ai — SOC 2 Type 2, GDPR/CCPA (added 2026-09-24)
94. https://console.groq.com/docs/prompt-caching — 50 % cached-input discount, gpt-oss models, 128–1,024-token minimum prefix, no stacking with batch (added 2026-09-24)

Not found despite searching: Groq Developer-plan numeric limits (login-gated; searched console.groq.com/docs/rate-limits twice — page now says the table *is* the Developer base table, re-check with an account); Cerebras Free-plan per-model numeric limits page on cerebras.ai/pricing (JS-rendered; used inference-docs instead); ~~Fireworks ToS text (PDF undecodable)~~ (resolved 2026-09-24, see [92]); DeepInfra free credits and bulk API docs; SambaNova inference data-retention (still unread after five more URLs, see §3) and structured-output model list beyond examples; Together free credits (confirmed none); SOC 2/ISO status for Groq/Together/Fireworks/SambaNova (trust pages JS-only) and DeepInfra (none published); a first-party Fireworks/DeepInfra base URL on a fetched page (marked unverified in §2).

---

## Verification log (2026-09-24)

Fact-check pass run the same day as the original fetch, again **without web search** (session budget exhausted); all re-verification used direct WebFetch of vendor pages plus local text extraction of the Fireworks ToS PDF. Quality rating: **acceptable** — the ranking in §8 survives; the errors were in transcription of the ArtificialAnalysis table, an overstatement of Together's data terms, and one Fireworks price row.

### Corrections applied, by severity

**Major (6)**
1. §5 AA line — SambaNova/Groq/DeepInfra numbers were read from the wrong columns ("Total Response" mistaken for TTFT; "Cost per Task" mistaken for blended $/1M); Together (84 tok/s) was in the table and had been omitted; Fireworks is the only absentee. Source: artificialanalysis.ai/models/gpt-oss-120b/providers.
2. §5 AA line, Cerebras — TTFT is 0.50 s (not 1.65 s); the "$0.23 vs $0.35/$0.75 discrepancy" was a category error (Cost per Task vs $/1M) and is withdrawn.
3. §3 Together bullet — "trains by default" was wrong; Together retains prompts by default (ZDR off) but training is explicit opt-in (privacy policy + ZDR doc [91]). Setting lives under Settings > Profile / Organization > Privacy.
4. §5 structural weaknesses — same Together correction.
5. §4.1 DeepSeek V4.1 Flash row — Fireworks docs price is $0.30/$0.006/$1.20 (the fireworks.ai/models card's $0.22/$0.66 disagrees); a "(US)" region variant at $0.45/$0.009/$1.80 exists; DeepInfra is $0.14 (0.004) / $0.42, promotional 30 % off, fp8 — not $0.09/$0.18.
6. (Counted with 3–4) §7 gotcha 6 and §8 verdict 5 reworded to "retains by default unless ZDR is toggled".

**Minor (8)**
7. §3 and §6 Together ToS clause quoted verbatim ("financial or medical information of any nature or any sensitive personal data") instead of the paraphrase "cannot transmit financial data".
8. §3 rate-limit table, SambaNova — MiniMax-M2.7 is Developer-only, not in the Free table.
9. §2 Together Responses API cell — "Not listed in the compatibility matrix" rather than a flat "No".
10. §7 gotcha 4 — strict-mode schema restrictions apply to all Cerebras models (`pattern`, `format`, `oneOf`/`allOf`/`not`, `minItems`/`maxItems`); Qwen3.8-27B additionally rejects `minLength`/`maxLength` in strict tools.
11. §4.1 Fireworks Priority tier — ~1.2–1.25× on checked rows; no general multiplier stated.
12. §7 gotcha 1 — Groq's page documents 429 only; per-request rejection at 8k TPM is inferred, marked unverified.

### Claims re-verified with sources (this pass)
- Together toggles and defaults: docs.together.ai/docs/zero-data-retention [91] — store prompts ON by default, training OFF by default, passthrough ON; org vs personal scope. Privacy page [44] still does not state defaults; console read-through by a human still recommended.
- AA column semantics + Endpoint Accuracy Index (SambaNova 98 %, DeepInfra 97 %, Cerebras 87 %, Groq 86 %, Together 77 %) [78] — added to §5.
- Groq prompt caching: 50 % cached-input discount on gpt-oss models, 128–1,024-token minimum prefix, no stacking with batch [94][6] — added to §4.1 and the §4.3 assumption line. Cerebras: caching is a capability with no cached price; cached tokens excluded from uncached TPM [12][14].
- Cerebras Developer totals: gpt-oss-120b 1k RPM / 1M uncached / 3M total TPM; qwen-3.8-27b 300 RPM / 150k uncached / 750k total (temporarily up from 450k) [12].
- Groq per-model max completion tokens (65,536 / 65,536 / 16,384 / 131,072) and ~500 tok/s for gpt-oss-120b [2].
- Fireworks US-only serverless at 1.5× from 2026-09-01 [25]; uncached prompt TPM ceilings 16.2M / 10.8M / 5.4M by size bucket [28]; legacy postpaid monthly caps $50 / $500 / $5,000 / $50,000 [27].
- DeepInfra practical RPM guidance (~12,000 @ 1 s, ~1,200 @ 10 s, ~200 @ 60 s) and sub-limit 429s during spikes [50].
- Ollama Free "starter models" restriction; Team = 10 concurrent, $1,000 shared [63].
- SambaNova per-model context windows (V3.2 preview 32k; MiniMax-M3 1M) [58]; MiniMax-M3 absent from the rate-limits page [57].
- Fireworks ToS PDF text-extracted [92]: §3.6 ZDR contractual, Response API / fine-tuning / agent features carved out, no financial-data clause, automated access permitted at human-plausible request rates.
- Cerebras SOC 2 Type 2 [93]; other five hosts' SOC 2 status not retrievable (JS trust centers / none published).
- Together status: further gpt-oss-120B incidents 09-22/23 and Kimi K3 incidents 09-02/06/08/10/13 [46]; Fireworks Qwen 3.8 Max degradation active again at check time [34]; Groq status components include retired models [11].

### Stale / unverified flags left in the document (all marked "(unverified as of 2026-09-24)")
1. No web-search sweep for announcements newer than the fetched pages (header).
2. Together September incident count (status page understated in the original §5 paragraph; now amended but still a snapshot).
3. Groq "100 % on every component" partly vacuous — retired components included.
4. DeepInfra DeepSeek-V4.1-Flash price is promotional (30 % off) and will change; DeepInfra deprecations land 2026-09-29.
5. Fireworks Qwen 3.8 Max degradation recurring while the status page shows 100 %.
6. Cerebras Code Pro/Max "Sold out" / GLM-4.7 is point-in-time; new plans announced via X/newsletter.
7. OpenRouter $0 text-model list churns weekly; any `:free` count is stale.
8. Groq rate-limits page now says the table is the Developer base table; re-check the "login-gated" note with an account.
9. SambaNova MiniMax-M3 preview limits unknown (not on the rate-limits page).
10. Cerebras "10× higher rate limits" is marketing copy; actual per-model ratios are 200× RPM / 33× uncached TPM for gpt-oss-120b.
11. Groq per-request rejection at 8k TPM is inferred, not documented (§7 gotcha 1).

### Still open after this pass
- SambaNova inference data-retention statement: five additional URLs 404/JS-only; unread.
- SOC 2 / ISO for Groq, Together, Fireworks, SambaNova (trust centers JS-rendered) and DeepInfra (nothing published).
- A human console read of Together's Settings > Profile / Organization > Privacy to confirm the [91] defaults on a live account.
