# NVIDIA Nemotron 3 Ultra / Super — research (as of 2026-09-24)

Research method note: the session's WebSearch budget was exhausted before this task started, so every fact below comes from direct WebFetch of primary pages (Hugging Face model cards, NVIDIA blogs and technical-report PDFs, OpenRouter's endpoints API, Ollama, DeepInfra, Nous Portal, Perplexity pricing, Artificial Analysis, Arena, Hacker News' Algolia API). Reddit could not be fetched (blocked host). Items marked "(unverified)" could not be confirmed from a fetched page.

> **NOT FACT-CHECKED.** Every other doc in this set carries a "Verification log" from an
> independent adversarial fact-check pass. This one does not: the checker for this doc failed with an
> API rate-limit error on 2026-09-24 and was not re-run. Treat every number here as single-sourced and
> unverified, and re-check before any decision depends on it. Nothing in
> `docs/superpowers/specs/2026-09-25-multi-model-platform-design.md` is load-bearing on this doc
> (Nemotron appears in no routing chain).
## 1. Snapshot

**Company.** NVIDIA Corporation. Nemotron is NVIDIA's open-weights model family; the stated strategy is "open weights, open data, open recipes" to drive agentic workloads onto NVIDIA hardware, with commercial hosting done by partners rather than by NVIDIA itself (NVIDIA's own hosted endpoint is a *trial* API, see §3) [16][49].

**Current lineup (text reasoning models)** — all are hybrid Mamba-2 + Attention + Mixture-of-Experts ("LatentMoE") with Multi-Token-Prediction heads, a switchable thinking mode, and 1M-token context (256K default in HF configs):

| Model | HF ID (BF16) | Params (total / active) | Context | Knowledge cutoff (pre / post-train) | Released | License |
|---|---|---|---|---|---|---|
| Nemotron 3 Ultra | `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16` (also `-NVFP4`, `-Base-BF16`, GenRM) | 550B / 55B | up to 1M | Sep 2025 / May 2026 | 2026-06-04 | OpenMDW-1.1 [3][9] |
| Nemotron 3 Super | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16` | 120B / 12B | up to 1M (256K default) | Jun 2025 / Feb 2026 | 2026-03-11 | NVIDIA Nemotron Open Model License [1] |
| Nemotron 3 Nano | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` (+ 4B variant) | 30B / 3.5B | up to 1M (256K default) | Jun 2025 / Nov 2025 | 2025-12-15 | NVIDIA Nemotron Open Model License [2] |
| Nemotron 3.5 Lightning | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` | 30B / 3B | up to 1M (256K on one H100) | Sep 2025 / May 2026 | 2026-08-11 | OpenMDW-1.1 [4] |

Adjacent Nemotron 3 releases: Nano Omni (multimodal: documents/audio/video, Apr 2026), Nemotron 3 Embed (Jul 2026), Nemotron 3 / 3.5 Content Safety, Nemotron ASR streaming [50][8]. Hosted API IDs differ from HF IDs: `nvidia/nemotron-3-super-120b-a12b` and `nvidia/nemotron-3-ultra-550b-a55b` on build.nvidia.com and OpenRouter [14][15][19][20].

**Modalities.** Ultra/Super/Nano/Lightning are text-only (tool calling, JSON output, thinking on/off). Vision/audio only via Nano Omni [50]. Languages: Ultra covers English, French, Spanish, Italian, German, Japanese, Hindi, Korean, Brazilian Portuguese, Chinese [3]; Super covers 7 languages [1].

**Release cadence.** Nano (Dec 2025) → Super (Mar 2026) → Ultra (Jun 2026) → 3.5 Lightning (Aug 2026) → NIM 2.0 serving optimizations for Ultra (Sep 10 2026) [2][1][3][4][12]. Roughly a major drop every 2–3 months; NVIDIA states it will keep "publishing more Nemotron models, datasets, and techniques" [49]. No Nemotron 4 date found.

**Positioning.** NVIDIA sells Ultra as "the best reasoning for mission-critical … multi-step workflows", Super as "highest accuracy, throughput reasoning, and tool calling … on multi-agent systems", Nano as "specialized sub-agents" [49]. The real differentiator is throughput per GPU, not top-line accuracy: the Ultra technical report claims "on-par accuracy" with GLM-5.1 / Kimi-K2.6 / Qwen-3.5 while delivering 5.9x / 4.8x / 1.6x their throughput at 8K-in/64K-out on GB200 [9][10]. Artificial Analysis at launch called Ultra "the leading US open weights model" (Intelligence Index 48) but behind Kimi K2.6 (54) [34]. Everything (weights, ~25T-token pretraining corpora, 40M post-training samples, RL environments, training code) is published, which is unusual even among open-weights labs [6][5][47].

## 2. Interfaces & surfaces

- **Consumer app (web/mobile/desktop):** None from NVIDIA. build.nvidia.com has a browser playground per model (browser use does not deduct trial credits) [17]. The consumer-facing surface for Nemotron is *Perplexity*: Perplexity uses Nemotron 3 Ultra "for search and Perplexity Computer" and in its agent router, and Nemotron 3 Super/Ultra are offered to Perplexity Pro subscribers [8][5][7]. The Ollama desktop app (macOS/Windows/Linux) exposes `nemotron-3-ultra:cloud`, `nemotron-3-super:cloud`, `nemotron-3-nano:cloud` [25][26][29].
- **Browser / OS integrations:** None first-party. Not found — searched: NVIDIA product page, Computex blog, developer blog tag page.
- **Voice:** No voice mode for the text models; separate Nemotron ASR streaming model (40 locales) and a Nemotron VoiceChat 11B model exist [8][42].
- **CLI / agentic coding tools:** NVIDIA lists day-one harness support for BlackBox AI, Cline, Factory AI, Hermes Agent, Kilo Code, LangChain Deep Agents, OpenClaw, OpenCode, OpenHands and Pi [8]. Via Ollama Cloud, `ollama launch claude` / `ollama launch codex` / `ollama launch opencode` wire Claude Code, Codex CLI and OpenCode to any cloud model, including Nemotron [28]. NVIDIA ships a `nemotron-customize` Claude Code marketplace plugin for training pipelines (not for using the model as a coder) [47]. No NVIDIA-branded coding CLI.
- **API + SDKs:** OpenAI-compatible Chat Completions everywhere: `https://integrate.api.nvidia.com/v1` (NVIDIA trial), OpenRouter, Ollama Cloud (`https://ollama.com/api/chat` plus OpenAI- and Anthropic-compatible clients), DeepInfra, Baseten, Together, Fireworks, FriendliAI, Venice, DekaLLM, Nous Portal, Perplexity API; cloud marketplaces on SageMaker JumpStart, Google Cloud/Vertex, Microsoft Foundry, OCI, Amazon Bedrock ("coming soon" as of March) [14][15][19][20][28][5][7]. Official SDK: none NVIDIA-specific — the docs use the `openai` Python package [14][15]. Self-host: vLLM, SGLang, TensorRT-LLM, Transformers, NIM containers (`nvcr.io/nim/nvidia/nemotron-3-ultra-550b-a55b`) [3][12].
- **OpenAI / Anthropic-compatible endpoints:** OpenAI-compatible on all of the above; Anthropic-compatible via Ollama Cloud [28].
- **MCP support:** No native MCP client (it is a model, not an agent product). Any MCP-capable harness (Claude Code via Ollama, OpenCode, Cline, Hermes Agent) works with it [28][8].
- **Batch API:** None found for NVIDIA-hosted or OpenRouter free endpoints. Not found — searched: build.nvidia.com model pages, docs.api.nvidia.com FAQ, OpenRouter endpoints.
- **Structured outputs:** `response_format` / `structured_outputs` supported on the OpenRouter free Super endpoint and on DeepInfra/DekaLLM paid endpoints; the free Ultra endpoint lists `tools`, `tool_choice`, `reasoning`, `reasoning_effort` but *not* `response_format` [21][22][19][20].
- **Tool use:** Native, with a `qwen3_coder`-style tool-call parser in vLLM/SGLang; JSON-schema tools supported [1][3]. Thinking is toggled via `extra_body={"chat_template_kwargs":{"enable_thinking":True}}` [15].
- **Computer-use / browser agent:** No first-party product; Perplexity Computer is built on it [8]. Ultra was post-trained on a BrowseComp search harness [10].
- **Scheduled / automated tasks, memory, projects/workspaces:** None (no NVIDIA consumer product). Not found — searched: NVIDIA product page, developer blog.
- **Messaging integrations (Telegram/Slack/WhatsApp/Discord):** None first-party. Not found — searched as above.
- **IDE plugins:** None first-party; Cline / Kilo Code / OpenCode / Continue-style plugins can point at any OpenAI-compatible endpoint [8].

## 3. Headless / server automation fit

- **Non-interactive use on macOS/Linux:** Excellent in the API sense — plain HTTPS Chat Completions, no browser session, no device login. Everything is `curl`-able [14][15][28].
- **Auth modes:**
  - NVIDIA trial: API key from build.nvidia.com (`NVIDIA_API_KEY` bearer) [14][15].
  - OpenRouter: API key; `:free` variants route to provider "Nvidia" (i.e. NVIDIA's own trial infrastructure) [21][22][23].
  - Ollama Cloud: `ollama signin` in the app/CLI or an API key from ollama.com/settings/keys (`OLLAMA_API_KEY`) [28].
  - Nous Portal: single Nous account sign-in, "one command in terminal" setup [32].
- **Consumer subscriptions used programmatically:** NVIDIA has no consumer subscription. The relevant subscriptions are third-party: Ollama Pro/Max explicitly include API usage credits, so programmatic use is the intended use [27][28]. Perplexity Pro's Nemotron access is a chat surface; programmatic Nemotron via Perplexity is a separate metered API (`perplexity/nemotron-3-ultra-550b-a55b`) [33]. Nous Portal tiers are credit bundles usable by the Hermes Agent CLI [32].
- **What the NVIDIA trial terms say (important for the "free" lane):** "NVIDIA will provide you access to the API Service for limited trial purposes only and without use of the API Service or Generated Content in production" (§1.2); "you may only use the API Service for internal testing and evaluation purposes, not in production" (§1.4); NVIDIA "will collect … User Content and Generated Content to improve NVIDIA products and services, including AI models" (§3.3(iv)); you must not upload confidential, personal or financial data (§2.6(a), §4.3); no scraping "robot, spider" use (§2.6(h)) [16]. Because the OpenRouter `:free` Nemotron endpoints are served by provider "Nvidia", these terms very likely govern them too [21][22][23] — treat free Nemotron as *evaluation-only, data-may-be-trained-on*.
- **Rate limits / caps:**
  - OpenRouter `:free`: 20 requests/min; 50 requests/day if you have bought < $10 credits lifetime, 1,000 requests/day once you have bought ≥ $10 lifetime; resets on UTC day [18].
  - OpenRouter free Ultra endpoint: 1,000,000-token context, 65,536 max completion tokens; free Super endpoint: 262,144 context, 235,929 max completion [21][22].
  - NVIDIA trial credits: deducted per remote API call; browser playground calls are free; exact credit grant and RPM Not found — searched: docs.api.nvidia.com FAQ and quickstart (404), build.nvidia.com model pages, Trial ToS (says only "subject to use limits defined by NVIDIA") [17][16]. (Community lore of "1,000 credits / 40 RPM" is unverified.)
  - Ollama Cloud: Free tier = "starter usage credits", 1 concurrent request, starter models only (list not published; Nemotron cloud models are not labelled starter) [27][29]; Pro = 3 concurrent, Max = 10 [27].
  - Paid OpenRouter endpoints have no platform-level request caps [18].
- **Sandboxing:** None provided — the model has no code-execution sandbox; your harness supplies it.
- **JSON / structured event output for orchestration:** OpenAI-style streaming (`stream: true`), `reasoning` / `include_reasoning` fields for exposing thinking tokens on OpenRouter, `response_format` on Super endpoints [19][20][21][22].
- **Session resume:** Stateless API; no server-side sessions or prompt caching on the free endpoints. DeepInfra and Ollama Cloud advertise cached-input pricing for Ultra ($0.10/M cached) [31][27].
- **Streaming:** Supported on every surface [19][20][28].

## 4. Cost

**Consumer / subscription tiers relevant to Nemotron** (NVIDIA itself sells none):

| Plan | $/mo | Includes | Caps |
|---|---|---|---|
| Ollama Cloud Free | $0 | starter usage credits, starter models only | 1 concurrent request [27] |
| Ollama Cloud Pro | $20 ($200/yr) | $60 usage credits/mo, concurrent models | 3 concurrent requests; unused credits do not roll over [27] |
| Ollama Cloud Max | $100 | $300 usage credits/mo | 10 concurrent [27] |
| Ollama Cloud Team | $500 | $1,000 shared credits/mo, unlimited users | 10 concurrent [27] |
| Nous Portal Free | $0 | free-tier models only, $0 credits | "standard rate limits" [32] |
| Nous Portal Plus / Super / Ultra | $20 / $100 / $200 | $22 / $110 / $220 credits, 200+ models, hosted tools | rollover caps $10 / $50 / $100 [32] |
| Perplexity Pro | ~$20 (unverified; price not fetched) | Nemotron 3 Super/Ultra selectable in-app [7][5] | chat surface only |
| OpenRouter (no plan) | $0, or ≥ $10 one-time credits | `:free` models | 20 RPM; 50/day or 1,000/day after $10 lifetime purchase [18] |

**API price per model ($/1M tokens):**

| Model | Provider | Input | Output | Cached | Notes |
|---|---|---|---|---|---|
| Ultra | OpenRouter `:free` (Nvidia) | $0 | $0 | — | 1M ctx, 65,536 max out [21] |
| Ultra | OpenRouter → DeepInfra (fp4) | $0.50 | $2.20 | — | 262K ctx, 16,384 max out [19] |
| Ultra | OpenRouter → BaseTen (fp4) | $0.60 | $2.40 | — | 202,800 ctx [19] |
| Ultra | OpenRouter → Venice (fp8) | $0.625 | $3.125 | — | 70% 30-min uptime at fetch time [19] |
| Ultra | DeepInfra direct | $0.50 | $2.20 | $0.10 | 256K, fp4 [31] |
| Ultra | Ollama Cloud | $0.10 | $3.00 | $0.10 | [27] |
| Ultra | Perplexity API | $0.25 | $2.50 | $0.25 | [33] |
| Ultra | Nous Portal | $0.50 | $2.20 | — | [32] |
| Super | OpenRouter `:free` (Nvidia) | $0 | $0 | — | 262K ctx, 235,929 max out, structured outputs [22] |
| Super | OpenRouter → DeepInfra (bf16) | $0.085 | $0.40 | — | 16,384 max out [20] |
| Super | OpenRouter → DekaLLM (fp8) | $0.08 | $0.45 | — | [20] |
| Super | Ollama Cloud | $0.015 | $0.60 | $0.015 | [27] |
| Super | Nous Portal | $0.08 | $0.45 | — | [32] |
| Nano 30B | Ollama Cloud / Nous | $0.06 / $0.05 | $0.24 / $0.20 | — | [27][32] |
| 3.5 Lightning | Nous Portal | $0.07 | $0.18 | — | [32] |
| NVIDIA build.nvidia.com | trial credits only, no list price | — | — | — | production requires a partner subscription [16] |

Batch pricing: none found on any provider. Together.ai's pricing page lists no Nemotron 3 chat models (only the ASR model at $0.0015/audio-min) [48].

**Monthly cost estimate — 150k input + 15k output tokens per job** (assumes each "job" is billed as one context of 150k in / 15k out; a real agent loop re-sends context per turn, so multiply by turns-without-caching; no batch discount exists):

| Path | per job | 10 jobs | 100 jobs | 1,000 jobs | Assumptions |
|---|---|---|---|---|---|
| (a) OpenRouter `:free` Ultra/Super | $0 | $0 | $0 | $0 (if ≤ 1,000 req/day) | needs a one-time $10 credit purchase for 1,000 req/day; at ~20–50 requests per agent job that is ~20–50 jobs/day max; NVIDIA trial ToS = non-production, content may train models [18][16] |
| (a) Ollama Cloud Pro ($20) — Ultra | $0.060 | $0.60 | $6.00 | $60.00 = exactly the $60 credit | $0.10 in / $3.00 out [27]; 1,000 jobs/month fits in Pro; 3 concurrent |
| (a) Ollama Cloud Pro ($20) — Super | $0.011 | $0.11 | $1.13 | $11.25 | $0.015 in / $0.60 out [27]; ~5,300 jobs/mo inside Pro credits |
| (a) Nous Portal Plus ($20) — Super | $0.019 | $0.19 | $1.88 | $18.75 | $0.08/$0.45 [32]; fits Plus |
| (a) Nous Portal — Ultra | $0.108 | $1.08 | $10.80 | $108 | needs Super tier ($100, $110 credits) [32] |
| (b) OpenRouter → DeepInfra Ultra | $0.108 | $1.08 | $10.80 | $108 | $0.50/$2.20 [19]; 16K max output per call |
| (b) OpenRouter → DeepInfra Super | $0.019 | $0.19 | $1.88 | $18.75 | $0.085/$0.40 [20] |
| (b) Perplexity API Ultra | $0.075 | $0.75 | $7.50 | $75 | $0.25/$2.50 [33] |
| (b) NVIDIA trial API | credits | — | — | — | not licensed for production [16] |

For scale: the same 1,000 jobs at Claude-class API pricing (e.g. Perplexity's listed `claude-sonnet-5` at $2/$10) would be ~$450 [33]. Nemotron Super at ~$19/1,000 jobs is roughly 25x cheaper; Ultra ~4x cheaper.

## 5. Strengths & weaknesses per reviews

**Benchmarks (vendor-reported, from the technical reports and model cards):**

| Benchmark | Ultra 550B (BF16) | Super 120B | Comparators (vendor's own table) |
|---|---|---|---|
| SWE-Bench Verified | 70.7 [3][10] | 60.47 (OpenHands), 59.2 (OpenCode), 53.7 (Codex) [11] | Ultra vs GLM-5.1 76.2, Kimi-K2.6 75.7, Qwen-3.5-397B 73.6 [10]; Super vs Qwen3.5-122B 66.4, GPT-OSS-120B 41.9 [11] |
| Terminal-Bench 2.1 / 2.0 | 56.4 (2.1) [3][10]; 54% (2.0) [5] | Term-Bench Core 2.0: 31.0; hard subset 25.78 [11] | Ultra vs GLM 59.3, Kimi 67.2, Qwen 49.9 [10]; Super vs Qwen3.5-122B 37.5, GPT-OSS 18.7 [11] |
| τ-Bench V3 / V2 | 70.9 (V3) [10] | 61.15 avg (V2) [11] | Ultra vs GLM 69.7, Kimi 72.4, Qwen 71.0; Super vs Qwen3.5-122B 74.53, GPT-OSS 61.0 |
| GDPVal | 46.7 [10] | — | GLM 54.7, Kimi 50.4, Qwen 34.6 |
| GPQA (no tools) | 87.0 [3] | 79.23 [11] | Super vs Qwen3.5-122B 86.6, GPT-OSS 80.1 |
| HLE (no tools / tools) | 26.7 / 37.4 [3] | 18.26 / 22.82 [11] | Super vs Qwen3.5-122B 25.3 |
| LiveCodeBench | 89.0 (v6) [3] | 81.19 (v5) [11] | Super vs Qwen 78.93, GPT-OSS 88.0 |
| MMLU-Pro | 86.8 [3] | 83.73 [1][11] | Super vs Qwen 86.7, GPT-OSS 81.0 |
| IFBench | 82% [5] | 72.56 [11] | Ultra vs GLM-5.1 77% |
| RULER @ 1M | 95.0 [10] | 91.64 [11] | Qwen-3.5 90.1 / 91.33; GPT-OSS-120B 22.3 (128K model) |
| Arena-Hard-V2 | — | 73.88 [11] | GPT-OSS-120B 90.26 |
| PinchBench (OpenClaw agents) | 91% [5] | 85.6% [6] | GLM-5.1 84%, Qwen3.5 89% |
| CVDP RTL/Verilog | 97.1% [13] | — | Kimi K2.6 95.2, GLM 5.2 92.1 |

**Third-party leaderboards:**
- Artificial Analysis: at launch (pre-release DeepInfra endpoint) Ultra scored Intelligence Index **48** — "leading US open weights model", vs Kimi K2.6 54, Gemma 4 31B 39, Nemotron 3 Super **36** — and was served at >300 tok/s vs 50–100 for DeepSeek/Kimi peers [34]. **Conflict:** AA's current open-source page (Index v4.3.2, re-weighted toward agentic evals and re-scaled) now shows "Nemotron 3 Ultra (Reasoning)" at **23**, 121 tok/s, $0.50 blended, 262K ctx, and lists MiMo-V2.6-Pro 46, GLM-5.3 45, Kimi K3 44, GLM 5.3 Flash 42, DeepSeek V4.1 Flash 39 as the top open weights [35][36]. Read: the index changed versions between June and September and newer Chinese releases have passed it; treat 48 vs 23 as non-comparable numbers.
- Arena (ex-LMArena) text leaderboard, 2026-09-13: `nvidia-nemotron-3-ultra-550b-a55b-nvfp4` rank **109 of 402**, score 1426±7, 10,693 votes; no Super entry [37]. Top of board is 1506 (claude-fable-5-high). So on human-preference chat it is mid-pack.

**What it is best at (attributed):**
- Throughput/cost per token at a given accuracy — NVIDIA's core claim (5.9x GLM-5.1, 4.8x Kimi-K2.6, 1.6x Qwen-3.5 on GB200) [9][10]; AA measured >300 tok/s at launch [34]; HN commenter throwa356262: "inference speed" is the notable strength, though it is "significantly bigger than Qwen for the same level of intelligence" [41].
- Long context: RULER @1M 95 (Ultra) / 91.6 (Super) with only ~11% speed loss from 1K to 512K per SignalBloom [10][11][46]; Corti ran Super with 1M context on two DGX Sparks [39].
- Instruction following / structured tool-call-heavy generation: IFBench 82 (Ultra) [5]; MTP speculative decoding yields ~30% fewer tokens per coding run, mainly on structured generation (Miraflow) [44].
- Openness: full datasets and training code; HN's dannyw: "Which other lab shares this?"; lambda: "full training code open" [42][46].
- RTL / chip-design coding (NVIDIA's own vertical) [13].
- Harness-tunable: LangChain got Deep Agents score from ~0.80 to 0.84–0.86 vs Opus 4.8's 0.87 by tuning message placement, not the model [45].

**Weak at (attributed):**
- Not frontier: behind GLM-5.1 / Kimi-K2.6 on SWE-Bench Verified (70.7 vs 76.2 / 75.7) and Terminal-Bench (56.4 vs 59.3 / 67.2) in NVIDIA's own table [10]; Arena rank 109 [37].
- Super is *below* Qwen3.5-122B-A10B on most agentic evals (τ-Bench 61 vs 75, Terminal-Bench Core 31 vs 37.5, SWE-Bench 60 vs 66) [11]; HN's anonym29: Qwen 3.5 122B "ends up being competitive with this on benchmarks" [40].
- Agentic reliability in practice: zacksiri (HN) — "I tested this model in an agentic workflow, it failed at some very basic tasks"; upmaru's three-turn test scored Super 2.0/10 output, noting it "made multiple attempts, and did not follow instructions" [40][43]. Neywiny (HN, Sep 2026): "Nemotron 550b is so dumb it's infuriating" for dev work [42]. daniele110199: Nemotron "looks smarter but stubborn" vs Qwen [42].
- Harness sensitivity: LangChain found identical instructions "did nothing" in tool descriptions but worked when injected into tool output; needed explicit compaction guidance or it answered from summaries instead of source files [45].
- Synthetic-data training raises hallucination concerns (anonym29) [40]; HLE 26.7 (Ultra) is modest [3].
- 1M context in practice needs NVFP4 on Blackwell; hosted endpoints expose 200–262K (DeepInfra/BaseTen/Venice) except the NVIDIA free endpoint (1M) [19][21][44].
- Hardware: Ultra needs 8x B200-class or 16x H100 to self-host [3]; Super 8x H100 [1]. Nothing here runs on a 16 GB Mac Mini except Nano 4B/Lightning quantizations (25 GB for Lightning BF16 → needs a 4-bit quant; unverified fit) [30].
- Datasets "open" but access requests reportedly "ignored for months" (nessex, HN) [42].
- Licensing: Super/Nano use the NVIDIA Open Model License with "aggressive patent retaliation triggers" and unilateral-change rights (SignalBloom) [46]; Ultra/Lightning moved to Linux Foundation OpenMDW-1.1 [3][4][5].

**Reliability / outage record:** No public status page found. OpenRouter endpoint uptime at fetch time: DeepInfra Ultra null, BaseTen 100%, Venice 70%, DekaLLM Super 97.6%, DeepInfra Super 100% [19][20]. Free endpoints returned no uptime figure [21][22]. **Controversies:** benchmark-index whiplash (48 → 23 across AA index versions) [34][35]; the dataset-access complaints above [42]; a widely shared HN view that the family exists "to keep people using … tools on their hardware" (cmrdporcupine) [42].

## 6. Finance / trading relevance

- **Real-time data access:** None built in; the model has no web browsing or market feed. Perplexity's search-grounded product uses Ultra internally, and the Perplexity API exposes `perplexity/nemotron-3-ultra-550b-a55b` (grounding depends on the Perplexity endpoint used, not the model) [8][33].
- **Market-data tools / connectors:** None first-party; bring your own tools (Alpaca/Tradier/Finnhub functions) via JSON tool calling, which is supported on all endpoints including the free ones [21][22].
- **Sentiment sources:** None built in.
- **Finance-specific products:** NVIDIA markets Nemotron 3.5 Lightning for "financial services workflows" as an always-on local execution layer [30]; no finance model variant.
- **Restrictions:** NVIDIA trial ToS forbids uploading "financial … information" or personal data and forbids production use [16]. That rules out the free NVIDIA/OpenRouter-free path for anything touching account data or live positions; paid partner endpoints (DeepInfra, Ollama Cloud) are governed by their own terms — Ollama states "We do not use them to train models" [28].
- **Fit:** Research summarization, filings/transcript digestion (1M context, RULER 95), sentiment classification and adversarial review of trade theses at very low cost. Not a data source and not a differentiated quantitative reasoner (HLE 26.7, GDPVal below GLM/Kimi) [3][10].

## 7. Integration recipe for our server

**Recommended path (two lanes):**
1. **Cheap paid lane (default):** Ollama Cloud Pro ($20/mo, $60 credits) → `nemotron-3-super:cloud` for bulk/cheap tasks and `nemotron-3-ultra:cloud` for heavier reasoning; OpenAI-compatible and Anthropic-compatible clients both work, key via `OLLAMA_API_KEY`, no training on prompts [27][28]. Alternative with identical model availability and per-token billing: OpenRouter → DeepInfra (`nvidia/nemotron-3-super-120b-a12b`, `nvidia/nemotron-3-ultra-550b-a55b`) [19][20].
2. **Free lane (evaluation only):** OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free` / `nvidia/nemotron-3-super-120b-a12b:free` after a one-time ≥ $10 credit purchase (1,000 req/day, 20 RPM) [18][21][22]. Use only for non-sensitive research/classification prompts, because the backing provider is NVIDIA's trial infrastructure whose ToS says non-production and content-may-train-models [16][23].

**Auth:** static API keys in the server's existing env-file plumbing; no OAuth/device flow anywhere.

**Minimal sketch (OpenAI SDK, works for all three surfaces by swapping base_url/key):**

```python
from openai import OpenAI
import os

SURFACES = {
    "ollama":     ("https://ollama.com/v1",          os.environ["OLLAMA_API_KEY"],     "nemotron-3-super"),
    "openrouter": ("https://openrouter.ai/api/v1",   os.environ["OPENROUTER_API_KEY"], "nvidia/nemotron-3-super-120b-a12b:free"),
    "nvidia":     ("https://integrate.api.nvidia.com/v1", os.environ["NVIDIA_API_KEY"], "nvidia/nemotron-3-super-120b-a12b"),
}
base, key, model = SURFACES["ollama"]
client = OpenAI(base_url=base, api_key=key)
resp = client.chat.completions.create(
    model=model,
    messages=[{"role": "system", "content": "Return JSON only."},
              {"role": "user", "content": "Classify this job request: ..."}],
    temperature=1.0, top_p=0.95, max_tokens=4000,          # NVIDIA's documented defaults [14][15]
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},  # thinking toggle [15]
    response_format={"type": "json_object"},                # supported on Super endpoints [20][22]
    stream=False,
)
print(resp.choices[0].message.content)
```

CLI equivalents: `ollama run nemotron-3-super:cloud "..."` (after `ollama signin`) [26][28]; `curl https://openrouter.ai/api/v1/chat/completions -H "Authorization: Bearer $OPENROUTER_API_KEY" -d '{"model":"nvidia/nemotron-3-ultra-550b-a55b:free","messages":[...]}'`.

**Task-class fit here:**
- Research / long-document digestion: good (1M context on free Ultra endpoint, RULER 95) [21][10].
- Classification / routing / triage: very good — Super at $0.011–0.019 per 150k-token job; structured outputs on Super [27][20].
- Chat (Telegram front-end): adequate, mid-pack on Arena (rank 109) [37].
- Adversarial review / second-opinion critic: good value as a *different-lineage* reviewer next to Claude, but not as a sole gate (below GLM/Kimi on agentic evals) [10].
- Coding / agentic build loops: usable with a tuned harness (LangChain: ~0.84–0.86 vs Opus 4.8 0.87 on Deep Agents) but community reports basic agentic failures for Super; keep Claude as primary [45][40][43].
- Trading research: fine for thesis critique and transcript summarization on paid lanes; never on the free lane with account data [16].

**Gotchas:**
- Free endpoints = NVIDIA trial ToS: non-production, prompts may train models, no financial/personal data [16][23].
- `:free` daily cap is per *request*, and agent loops burn 20–60 requests per job [18].
- DeepInfra Ultra caps completions at 16,384 tokens; use BaseTen (182K) or the free NVIDIA endpoint (65K) for long generations [19][21].
- Free Ultra endpoint lacks `response_format`; use tool-calling to force JSON [21].
- Thinking mode is a chat-template kwarg, not `reasoning_effort` alone; budget it explicitly or long reasoning eats the output cap [15][44].
- Message placement matters more than wording (inject guidance in tool results, not system prompt) [45].
- Hosted context is 200–262K on most paid providers despite the 1M headline [19][20].
- Ollama Free tier "starter models" list is unpublished; assume Nemotron needs Pro [27][29].
- Nothing in the Ultra/Super tier runs locally on a 16 GB M4; only Nano-4B / Lightning quantizations would [3][1][30].

## 8. Verdict

1. Nemotron 3 Ultra (550B-A55B) and Super (120B-A12B) are open-weights, US-built, hybrid Mamba/MoE models whose real edge is throughput and price, not top accuracy; they trail GLM-5.1 / Kimi-K2.6 on agentic coding and sit at Arena rank 109.
2. They are the cheapest frontier-scale option we can reach: ~$0.01–0.02 per 150k-token job (Super) and ~$0.06–0.11 (Ultra), fitting comfortably inside a $20/mo Ollama Cloud Pro or Nous Portal Plus subscription — matching the owner's subscription-over-metered preference.
3. The OpenRouter `:free` lane works (1M context, tools) but is NVIDIA trial infrastructure: non-production terms, prompts may train models, 1,000 req/day — evaluation and non-sensitive research only.
4. Headless fit is excellent (plain OpenAI-compatible HTTPS, API keys, streaming, tool calling), with zero consumer-product surfaces to integrate.
5. Best roles here: cheap classification/routing, long-document research, and a second-lineage adversarial reviewer; keep Claude as the primary coding/agentic engine.

Fit scores (1–10): research **7**, coding/agentic **5**, cost efficiency **9**, automation friendliness **8**, trading research **5**.

## 9. Sources

All accessed 2026-09-24.

1. https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16
2. https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16
3. https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16
4. https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16
5. https://developer.nvidia.com/blog/nvidia-nemotron-3-ultra-powers-faster-more-efficient-reasoning-for-long-running-agents/
6. https://developer.nvidia.com/blog/introducing-nemotron-3-super-an-open-hybrid-mamba-transformer-moe-for-agentic-reasoning/
7. https://blogs.nvidia.com/blog/nemotron-3-super-agentic-ai/
8. https://blogs.nvidia.com/blog/nvidia-gtc-taipei-computex-2026-news/
9. https://research.nvidia.com/labs/nemotron/Nemotron-3-Ultra/
10. https://research.nvidia.com/labs/nemotron/files/NVIDIA-Nemotron-3-Ultra-Technical-Report.pdf (Figure 1 values extracted from PDF text)
11. https://research.nvidia.com/labs/nemotron/files/NVIDIA-Nemotron-3-Super-Technical-Report.pdf (Table 5 extracted from PDF text)
12. https://developer.nvidia.com/blog/how-full-stack-nim-optimizations-deliver-2-5x-more-users-on-nemotron-3-ultra/
13. https://developer.nvidia.com/blog/nvidia-nemotron-3-ultra-leads-open-models-on-accuracy-and-efficiency-in-agentic-rtl-coding/
14. https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b
15. https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b
16. https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf
17. https://docs.api.nvidia.com/nim/docs/faq
18. https://openrouter.ai/docs/api-reference/limits
19. https://openrouter.ai/api/v1/models/nvidia/nemotron-3-ultra-550b-a55b/endpoints
20. https://openrouter.ai/api/v1/models/nvidia/nemotron-3-super-120b-a12b/endpoints
21. https://openrouter.ai/api/v1/models/nvidia/nemotron-3-ultra-550b-a55b:free/endpoints
22. https://openrouter.ai/api/v1/models/nvidia/nemotron-3-super-120b-a12b:free/endpoints
23. https://openrouter.ai/provider/nvidia
24. https://openrouter.ai/docs/features/privacy-and-logging
25. https://ollama.com/library/nemotron-3-ultra
26. https://ollama.com/library/nemotron-3-super
27. https://ollama.com/pricing
28. https://docs.ollama.com/cloud
29. https://ollama.com/search?q=nemotron and https://ollama.com/search?c=cloud
30. https://ollama.com/library/nemotron-3.5-lightning
31. https://deepinfra.com/models?q=nemotron
32. https://portal.nousresearch.com/
33. https://docs.perplexity.ai/getting-started/pricing
34. https://artificialanalysis.ai/articles/nvidia-nemotron-3-ultra-launch-announced
35. https://artificialanalysis.ai/models/open-source
36. https://artificialanalysis.ai/methodology/intelligence-benchmarking
37. https://arena.ai/leaderboard/text
38. https://hn.algolia.com/api/v1/search?query=nemotron%203%20ultra&tags=story
39. https://hn.algolia.com/api/v1/search?query=nemotron%203%20super&tags=story
40. https://hn.algolia.com/api/v1/items/47337803
41. https://hn.algolia.com/api/v1/items/48398107
42. https://hn.algolia.com/api/v1/search?query=nemotron&tags=comment&hitsPerPage=50
43. https://upmaru.com/llm-tests/simple-tama-agentic-workflow-q1-2026/nemotron-3-super-120b
44. https://miraflow.ai/blog/nemotron-3-ultra-explained-nvidia-hybrid-mamba-moe-2026
45. https://www.langchain.com/blog/tuning-the-harness-not-the-model-a-nemotron-3-ultra-playbook
46. https://www.signalbloom.ai/posts/nvidia-nemotron-3-super-is-a-bigger-deal-than-you-think/
47. https://github.com/NVIDIA-NeMo/Nemotron
48. https://www.together.ai/pricing
49. https://www.nvidia.com/en-us/ai-data-science/foundation-models/nemotron/
50. https://huggingface.co/nvidia/models?search=Nemotron-3
