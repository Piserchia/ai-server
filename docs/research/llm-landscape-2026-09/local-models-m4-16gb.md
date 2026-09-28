# Local models on an M4 Mac Mini 16GB — research (as of 2026-09-24)

Scope: what open-weight models fit on the server's M4 Mac mini (16 GB unified memory, 10-core GPU, 120 GB/s [2]) while Postgres, Redis and the Python runner hold roughly 4-6 GB, which runtime to use (Ollama / llama.cpp / MLX / LM Studio), what small models are reliable for, and a concrete recommendation. Method note: the web-search budget was exhausted before this task started, so every fact below comes from directly fetched primary pages (Ollama library, Hugging Face model cards, llama.cpp/MLX docs) and Hacker News comment threads via the Algolia API. Reddit could not be fetched. Numbers I could not verify are marked "(unverified)" or "(unverified as of 2026-09-24)"; numbers I derived are marked "(computed)". A fact-check pass on 2026-09-24 applied the corrections and additions recorded in the Verification log at the end. A second gap-fix pass the same day (web search budget again exhausted; primary pages fetched directly) corrected the Anthropic-compatibility claim in §2, added the Apple Foundation Models framework evaluation in §7, and added the cross-doc router dimensions (data handling, progress visibility, third-party serving, reliability, Telegram latency, tool churn, calibrated fit scores) in §8.

## 1. Snapshot

**"Company":** there is no single vendor. The relevant producers are Alibaba (Qwen), Google (Gemma), OpenAI (gpt-oss), Mistral (Ministral), Microsoft (Phi), Meta (Llama), DeepSeek (R1 distills) and Zhipu/Z.ai (GLM). The runtime layer is Ollama (MIT, v0.34.4 released 2026-09-23 [41][48]), llama.cpp (MIT, Homebrew 0.5.0 [54]), Apple's mlx-lm [6] and LM Studio [19].

**Lineup that plausibly fits in ~8-10 GB of model memory (the budget after services, see §3):**

| Model (Ollama tag) | Params | Default quant / download | Context | Modalities | Knowledge cutoff | License | Source |
|---|---|---|---|---|---|---|---|
| `qwen3.5:9b` | 9B, hybrid Gated-DeltaNet + attention (dense, not MoE — the card's highlight text says "Gated Delta Networks combined with sparse Mixture-of-Experts", which is family boilerplate; `config.json` has no MoE fields: 32 layers, 16 Q / 4 KV heads, head_dim 256) | Q4_K_M 6.6 GB; q8_0 11 GB; `9b-mlx` 8.9 GB | 256K native (262,144), 1M w/ YaRN | text, image, video in | not stated on card | Apache 2.0 | [8][20][40] |
| `qwen3.5:4b` | 4B, same hybrid | Q4_K_M 3.4 GB; q8_0 5.3 GB; `4b-mlx` 4.0 GB | 256K | text, image, video | not stated | Apache 2.0 | [8][28][40] |
| `qwen3.5:2b` / `0.8b` | 2.3B / 0.8B | default tags are **q8_0**: 2.7 GB / 1.0 GB (`2b-q4_K_M` 1.9 GB; no Q4 tag for 0.8b) | 256K | text, image | not stated | Apache 2.0 | [8] |
| `gemma4:12b` | 11.95B dense, encoder-free multimodal | 7.6 GB (`12b-mlx` 7.7 GB) | 256K | text, image, audio (30 s), video (60 s @1 fps) | January 2025 | Apache 2.0 | [9][29] |
| `gemma4:e4b` / `e2b` | 4.5B eff. (8B total incl. PLE) / 2.3B eff. | 9.6 GB / 7.2 GB (note: large downloads for the param count) | 128K | text, image, audio | January 2025 | Apache 2.0 | [9][47] |
| `qwen3:8b` / `qwen3:4b` / `qwen3:14b` (previous gen, Apr-Jul 2025) | 8.2B / 4B / 14B dense | 5.2 / 2.5 / 9.3 GB | 8b/14b 40K (32K native, 131K YaRN); the current `qwen3:4b` tag (2507 refresh) is listed at 256K | text | not stated | Apache 2.0 | [4][53] |
| `gpt-oss:20b` | 21B total / 3.6B active MoE | MXFP4 only, 14 GB download; ~11-13 GB resident | 128K | text | not stated on Ollama/HF pages (unverified) | Apache 2.0 | [3][30][57] |
| `ministral-3:8b` / `3b` / `14b` | 8.4B LM + 0.4B vision / 3B / 14B | 6.0 / 3.0 / 9.1 GB | 256K | text, image | not stated | Apache 2.0 | [10][43] |
| `granite4.2:3b` / `8b` (IBM, released 2026-08-25, on Ollama 3 weeks ago) | 3B / 8B dense GQA, built-in `<think>` | 2.2 GB / 5.3 GB default (same size as the `q4_K_M` tags; q8_0 3.9 / 9.3 GB) | 128K native (512K extension) | text only | not stated | Apache 2.0 | [60][61][62] |
| `phi4-mini` | 3.8B | 2.5 GB | 128K | text | June 2024 (public data) | MIT | [11][32] |
| `llama3.2:3b` / `1b` | 3B / 1B | 2.0 / 1.3 GB | 128K | text | not stated on page | Llama 3.2 license | [36] |
| `deepseek-r1:8b` (0528 = Qwen3-8B distill) | 8B | 5.2 GB | 128K | text | not stated | MIT | [12][31] |
| GLM-4.7-Flash (30B-A3B MoE) | 31B total / 3B active | not on Ollama library; HF BF16 only, MIT | 131K (unverified as of 2026-09-24: the card fetch surfaced only `max_new_tokens` 131072, not an explicit context window) | text | not stated | MIT | [33] |
| Gemma 3 (`gemma3:4b` 3.3 GB, `12b` 8.1 GB, `12b-it-qat`) | 4B / 12B | Q4 / QAT | 128K | text, image | superseded by Gemma 4 | Gemma terms | [5] |

**Too big for this box (listed so nobody tries):** `qwen3.5:27b` 17 GB, `qwen3.6:35b` (MoE 3B active) 24 GB, `qwen3.8:27b` 18 GB (the smallest of the 12 `qwen3.8` tags; there is still no Qwen3.6/3.8 variant under 10 GB [63]), `qwen3.8-flash-next` (125B-A6B, 105 GB, `125b-mlx` only, **Qwen Community License 1.0 — Qwen's newest line is no longer Apache 2.0**, 2 weeks ago [65]), `muse-glimmer:30b` (Meta, Apache 2.0, 18 GB / 19 GB mlx, 128K, text+image, tools+thinking, 3 weeks ago [66]), `gemma4:26b` (25.2B/3.8B-active MoE) 19 GB, `gemma4:31b` 20 GB, `gpt-oss:120b` 65 GB, `granite4.2:30b` 18 GB [60], DeepSeek-V4-Pro, `deepseek-v4.1-flash` (552B-backbone MoE, cloud-only tag, 2 weeks ago [67]), GLM-5.x [1][8][9][3].

**Release cadence:** roughly quarterly per family. Ollama's library on 2026-09-24 shows Qwen3.5 (Feb 2026) → Qwen3.6 → Qwen3.8 (1 month ago), Gemma 4 (arXiv 2607.02770, July 2026 per card; Ollama tags 5 months → "yesterday" for the newest MLX builds), Ministral 3 (Dec 2025), gpt-oss (Aug 2025), GLM-5.1/5.2/5.3 (2026), Granite 4.2 (Aug 2026 [61]); the newest Ollama arrivals are `qwen3.8-flash-next` and `deepseek-v4.1-flash` (both 2 weeks ago, both far outside this box's envelope [65][67]) [1][20][29][43]. Expect the "best 4B-9B" answer to change every ~3 months.

**Positioning (one paragraph):** on a 16 GB Mac shared with a database and a job runner, local inference is a **cheap, private, always-on sidecar for bounded tasks** (classification, routing, extraction, summarization, embeddings), not a replacement for Claude on agentic work. The strongest 2026 options in the fit envelope are Qwen3.5-9B (best tool-calling and benchmark scores per size [20][59]) and Gemma 4 12B (higher MMLU-Pro/LiveCodeBench, larger memory footprint [29]); community on HN rates the two "not far off" each other [27]. gpt-oss-20b is technically runnable on a 16 GB Mac with nothing else loaded [23][30], but not alongside 4-6 GB of services.

## 2. Interfaces & surfaces

- **Consumer app:** Ollama ships a macOS app (dmg) with a chat UI [48 docs macos]; LM Studio is a desktop GUI with an embedded server [19][39]. Neither has mobile clients; there is no browser/OS integration or voice layer in the runtime itself (Gemma 4 accepts audio *input* up to 30 s [29]).
- **CLI / agentic tools:** `ollama run <model>`, `ollama pull`, `ollama ps` [3][17]; `lms server start|stop`, `lms load <model> --context-length N --gpu max`, `lms ls`, `lms ps`, `lms unload --all` [19]; `llama-server -m model.gguf -c 8192 --jinja` [22]; `mlx_lm.server --model <hf-repo>` (port 8080) [38]. Coding agents (Claude Code-style loops) can point at these OpenAI-compatible endpoints, but see §5 for why that works poorly with ≤14B models.
- **API + SDKs:** Ollama native REST at `http://localhost:11434/api/{chat,generate,embed,ps,show}` with official Python (`ollama`) and JS SDKs [49][58]; OpenAI-compatible `http://localhost:11434/v1/{chat/completions,completions,embeddings,models,responses}` usable from the `openai` Python SDK with `api_key='ollama'` [7]. llama-server exposes `/v1/chat/completions`, `/v1/embeddings`, `/v1/responses` [22]. mlx_lm.server exposes `/v1/chat/completions` and `/v1/models` [38].
- **Anthropic-compatible endpoint (corrected 2026-09-24; the earlier "none" contradicted runtimes-aggregators.md and was wrong):** Ollama exposes `POST http://localhost:11434/v1/messages` (and `https://ollama.com/v1/messages` for cloud models) — supported: "Messages, Streaming, System prompts, Multi-turn conversations, Vision (images), Tools (function calling), Tool results, Thinking/extended thinking"; **unsupported: `tool_choice`, `metadata`, prompt caching, the Batches API, PDF document blocks** [75]. Claude Code / the Agent SDK can therefore be pointed at a local model with `ANTHROPIC_AUTH_TOKEN=ollama`, `ANTHROPIC_BASE_URL=http://localhost:11434`, empty `ANTHROPIC_API_KEY`, then `claude --model <tag>`; `ollama launch claude` writes that config for you (`ollama launch` also targets OpenCode, Codex, VS Code and Droid) [76][89]. Ollama's own guide warns that "tool-calling support varies" per model and recommends ≥64K context for larger repos [76] — on this box a 64K context alone is ≈4.6 GB of q8 KV for a dense 8B (computed from §3), so the endpoint is a real integration path for **bounded, schema-shaped sub-jobs** dispatched through the existing Agent SDK plumbing, not for running the coding loop locally (see §5). llama.cpp's `llama-server` and `mlx_lm.server` still expose only OpenAI-style routes [22][38]. The `ANTHROPIC_*` env vars point at localhost, not at Anthropic, so this stays inside the no-API-key policy.
- **Apple Foundation Models framework (macOS 26+):** a fifth local surface, evaluated in §7 — Apple's ~3B on-device model behind a Swift API (`LanguageModelSession`, `@Generable` guided generation, `Tool` calling, streaming), reachable from Python only through third-party OpenAI-compatible shims (`afm`, `apple-on-device-openai`) [77][78][82][83].
- **MCP:** not a runtime feature; the client (your Python code, Qwen-Agent, etc.) supplies tools. Qwen-Agent has MCP config support [53].
- **Batch API:** none; you batch yourself (llama-server `-np N` parallel slots [22]; Ollama `OLLAMA_NUM_PARALLEL` [17]).
- **Structured outputs:** Ollama `format=<JSON schema>` (also via OpenAI `response_format`) [15]; llama-server `--json-schema` / `--grammar` (GBNF) [22]; LM Studio MLX engine enforces schemas with Outlines (regex token masking) [55]; Ollama v0.33.1 added structured outputs on its MLX runner and v0.34.4 made them single-pass on thinking models [41].
- **Tool use:** Ollama `tools=[...]` in `/api/chat`, streaming and parallel tool calls supported; the docs' *single-shot* recipe is "only recommended for models which only return a single tool call"; streaming with tools is not itself restricted, and a parallel-tool-calling section is documented [16]. llama-server needs `--jinja` [22]. OpenAI-compat layer does **not** support `tool_choice` or logprobs [7].
- **Computer-use / browser agent:** none built in. Qwen3.5 cards report ScreenSpot-Pro scores (65.2 for 9B) [20], i.e. the vision model can do GUI grounding, but nothing here drives a browser.
- **Scheduled tasks / memory / projects / messaging integrations / IDE plugins:** none in the runtimes; those are your server's job (launchd + Telegram already exist). LM Studio can auto-start its server on login and JIT-load models [39].
- **Thinking control:** Ollama `think: true|false|null|<level string>` (levels are model-specific, listed in the model's `thinking.values`; gpt-oss exposes low/medium/high) returns `message.thinking` separately [50]; Qwen3.5 thinks by default (`enable_thinking: False` to disable) [28]; gpt-oss has low/medium/high effort and requires the harmony format [30].

## 3. Headless / server automation fit

- **Non-interactive use:** Ollama runs as a launchd service via `brew install ollama && brew services start ollama` (formula 0.34.4) [48]; env vars for the app are set with `launchctl setenv OLLAMA_HOST ...` then restart [17]. llama.cpp is a plain binary (`brew install llama.cpp`, 40+ binaries incl. `llama-server`, `llama-bench`) [54]. LM Studio offers "llmster", a server-native daemon installed with `curl -fsSL https://lmstudio.ai/install.sh | bash`, or the desktop app in headless mode [39]. mlx_lm.server explicitly "is not recommended for production as it only implements basic security checks" [38].
- **Auth:** none locally; API key is ignored on the Ollama OpenAI endpoint [7]. No OAuth, no subscription sign-in, no terms restricting programmatic use — local inference is "always unlimited" per Ollama's pricing page [37]. Model licenses: Apache 2.0 (Qwen3.5, Gemma 4, gpt-oss, Ministral 3, Granite 4.2 [61]; note Qwen3.8-Flash-Next moved to the Qwen Community License 1.0 [65]), MIT (Phi-4-mini, DeepSeek-R1 distills, GLM-4.7-Flash), Gemma terms for EmbeddingGemma and Gemma 3 [20][29][30][43][32][31][33][46][5].
- **Rate limits / caps:** hardware only for Ollama/llama.cpp/LM Studio (the Apple framework is the exception: one request per session at a time, and a reported throttle for non-foreground/CLI processes — §7). Ollama defaults: context 4096 tokens (`OLLAMA_CONTEXT_LENGTH` / `num_ctx`), 1 parallel request per model (`OLLAMA_NUM_PARALLEL`), up to 3 loaded models (`OLLAMA_MAX_LOADED_MODELS`), models unload after 5 min (`OLLAMA_KEEP_ALIVE`, `keep_alive: -1` to pin, `0` to unload immediately) [17].
- **The memory budget (the real cap):**
  - Metal lets a process wire roughly **2/3 of unified memory on ≤32 GB Macs** (≈10.7 GB of 16 GB) by default, 75% above 32 GB [52][45]. Override: `sudo sysctl iogpu.wired_limit_mb=<MB>` (resets on reboot; `/etc/sysctl.conf` to persist) [52][25]. Commenters warn overshooting causes driver glitches and swap thrash [25][52].
  - After 4-6 GB for Postgres/Redis/runner plus macOS itself, the safe envelope is **~7-9 GB for weights + KV cache + compute buffers** (computed). That admits Qwen3.5-9B Q4 (6.6 GB) or Gemma 4 12B Q4 (7.6 GB) with a small context, Qwen3.5-4B (3.4 GB) comfortably, and **not** gpt-oss-20b (11-13 GB resident per HN reports [23]) or qwen3:14b (9.3 GB) without evicting services.
  - KV cache is the hidden cost: for dense Qwen3-8B (36 layers, 8 KV heads, head dim 128 [53]) f16 KV is ≈144 KB/token, so 8K context ≈1.15 GB and 150K context ≈21 GB (computed). `OLLAMA_KV_CACHE_TYPE=q8_0` halves it, `q4_0` quarters it (global setting) [17]; llama-server `-ctk q8_0 -ctv q8_0` [22]. Qwen3.5's hybrid stack (3 Gated-DeltaNet blocks per 1 attention block [28]) should cut attention KV by roughly 4x versus dense (computed from the layer ratio; not benchmarked).
  - `OLLAMA_NUM_PARALLEL` multiplies KV memory ("2K context with 4 parallel requests = 8K") [17]; keep it at 1 on this box.
- **Sandboxing:** none; local models are as sandboxed as the Python process calling them. Prompt-injection risk is the same as any model; the mitigation is that local calls have no tools unless you give them.
- **Structured event output:** Ollama streams NDJSON with `message.thinking`, `message.content`, `message.tool_calls`, and returns `eval_count`, `eval_duration` (ns), `prompt_eval_count`, `total_duration` for tok/s telemetry [49].
- **Session resume:** none server-side (Ollama Responses API is non-stateful [7]); you replay `messages`. Prompt caching: llama-server reuses KV across slots; mlx-lm has prompt caching and rotating KV cache [6]; LM Studio's MLX engine caches KV (8B, 3K context: 10 s → 0.11 s re-prompt) [55].
- **Streaming:** yes on all four runtimes [7][22][38][55].

## 4. Cost

**Consumer plans:** local inference is free on all runtimes. Ollama's cloud tiers (only relevant if you want a hybrid escape hatch): Free $0 with starter credits; Pro $20/mo or $200/yr with $60/mo usage credits and 3 concurrent requests; Max $100/mo with $300/mo credits and 10 concurrent; Team $500/mo (shared $1,000 credits) [37]. LM Studio: free, `lms` CLI MIT-licensed [19]. Ollama cloud does **not** support structured outputs [15].

**Ollama Cloud escape hatch, assessed:** 19 cloud models on 2026-09-24 — `gemma4` 12b/26b/31b, `qwen3.5` 0.8b-122b, `gpt-oss` 20b/120b, `nemotron-3` nano/super/ultra, `glm-5.1/5.2/5.3(-flash)`, `deepseek-v4-flash/-pro/-v4.1-flash`, `kimi-k2.6/k2.7-code/k3`, `minimax-m2.7/m3`, `mistral-large-3` [71]. Auth is an Ollama account: either `export OLLAMA_API_KEY=...` or signing in through the app/CLI; prompts and responses are processed on Ollama's servers ("We do not use them to train models"), and cloud features can be disabled to stay local-only [72]. **Policy fit:** it is *not* an Anthropic key, but it is a per-account API key on a metered credit tier ($60-$300/mo of credits above the free starter), data leaves the box, and structured outputs are unsupported — so it is outside the local/no-key path this doc recommends and would need an explicit owner decision like any other paid API. The hybrid option below is therefore listed for completeness, not recommended.

**API price per model:** $0/token locally. The only bills are hardware (sunk), electricity and the Claude Max subscription you already pay for the real work. **Electricity/thermal:** Apple rates the M4 Mac mini at 4 W idle / 65 W max (14 / 222 BTU/h) [73]; sustained GPU inference on the base M4 has not been measured here, so take 35-65 W as the bracket (computed from Apple's max; the true GPU-only figure is unverified). At 65 W worst case: the 100-job right-sized column below (≈3.3 h GPU) is ≈0.2 kWh ≈ $0.03-0.07/month at $0.15-0.30/kWh; 1,000 right-sized jobs (≈33 h) ≈ 2.1 kWh ≈ $0.3-0.6; the 100-job 150k-token scenario (≈54 h) ≈ 3.5 kWh ≈ $0.5-1.1 (computed). Thermally, 222 BTU/h is a light-bulb's worth of heat; the mini will throttle before it becomes a room problem, which shows up as lower t/s, not failures.

**Reference hosted prices for the same weights** (for comparison only, Artificial Analysis): Qwen3.8 27B $0.5/1M blended, Qwen3.6 35B-A3B $0.6, Meta Muse Glimmer 30B $0.2 [21]. Gemma 4 26B-A4B is listed at $0.1/1M on the same page [21]. Small 4-9B models are essentially free-tier on most hosts (unverified as of 2026-09-24 — not fetched).

**Throughput anchors for the M4 base (10 GPU cores, 120 GB/s):** llama.cpp's own benchmark table gives LLaMA-7B Q4_0 **221 t/s prompt processing (pp512), 24.1 t/s generation (tg128)**; Q8_0 13.5 t/s; F16 7.4 t/s [2]. Generation is bandwidth-bound (120 GB/s ÷ weight bytes is the ceiling, computed): ≈35 t/s for a 3.4 GB 4B Q4 model, ≈18 t/s for a 6.6 GB 9B Q4 model, ≈16 t/s for 7.6 GB Gemma 4 12B, before KV overhead. Anecdotes: "10-15 tok/s on M4" for an unspecified Qwen3 (Analemma_, 2025-10-28) [56]; Gemma-4-E4B MLX ≈10.5 t/s on an M4 MacBook Air 32 GB (ionwake, 2026-05-11) [56]. All the fast numbers on HN (45-108 t/s) are M4 Pro/Max/M3 Ultra/M5 Pro and do **not** transfer [56][59][27].

**No measured throughput or memory on the actual server box** — every number in this section is llama.cpp's LLaMA-7B table, HN anecdotes, or bandwidth arithmetic. A 10-minute run would replace all of the "(computed)" figures and should be the first step of §7:

```bash
brew install llama.cpp                                    # llama-bench [54]
llama-bench -m ~/.ollama/models/<qwen3.5-4b-Q4_K_M>.gguf -p 512 -n 128 -t 4   # pp512 / tg128 [2]
llama-bench -m ~/.ollama/models/<qwen3.5-9b-Q4_K_M>.gguf -p 512 -n 128 -t 4
ollama run qwen3.5:4b --verbose "Summarize: ..."            # prints prompt eval / eval rate (t/s)
ollama run qwen3.5:9b --verbose "Summarize: ..."
ollama ps                                                  # resident size + 100% GPU? [3][17]
vm_stat | head -5                                          # free pages with the model loaded and Postgres up
```

Record pp t/s, tg t/s, `ollama ps` resident GB at `num_ctx` 8192 with services running; those four numbers decide whether the 9B tier is usable here at all. **Why the web cannot substitute for the run (checked again 2026-09-24):** three further HN queries for base-M4 / 16 GB figures returned no usable Qwen3.5 numbers — the only 16 GB M4-mini owners who post about Qwen3.5-4B (mingodad 2026-03-08, brainless 2026-09-02) publish no t/s, the "45-55 t/s" base-M4 report is an Air offloading to an M1 Ultra Studio, and the one Qwen3.5-4B figure (186 t/s MetalRT / 87 t/s llama.cpp) is an M4 Max [90]. The only published base-M4 row remains llama.cpp's 7B Q4_0 table (221 pp / 24.1 tg) [2]. If the run itself is the blocker, `ollama` also reports `size_vram` and `context_length` per loaded model on `GET /api/ps`, so the memory half of the measurement is one curl away [88].

**Monthly cost to run 10 / 100 / 1000 agent jobs at the spec'd 150k input + 15k output tokens/job:**

Assumptions: (a) "subscription" = the machine you own, cost expressed as wall-clock GPU time because dollars are ~0; (b) "API" = the same weights on a hosted small-model tier, at the AA-listed ~$0.5/1M blended for a 27B-class Qwen (9B-class would be cheaper; unverified) [21]; (c) M4 base speeds from the anchors above with pp ≈150 t/s and tg ≈16 t/s for Qwen3.5-9B Q4 after KV overhead (computed estimate, not measured); (d) a 150k-token prompt does not fit a dense 8-9B model's KV on this box at all (≈21 GB f16, ≈10.5 GB q8_0, computed) — so column (a) is only feasible with the hybrid Qwen3.5 or by chunking, and is shown to make the infeasibility explicit.

| Jobs / month | (a) Local Qwen3.5-9B Q4, wall-clock (150k in / 15k out) | (a') Local, right-sized job (8k in / 1k out) | (b) Hosted small-model API @ ~$0.5/1M |
|---|---|---|---|
| 10 | ≈5.4 h GPU time (≈32 min/job); $0 | ≈20 min total (≈2 min/job); $0 | ≈$0.83 |
| 100 | ≈54 h (≈2.3 days of 100% GPU); $0 | ≈3.3 h; $0 | ≈$8.25 |
| 1,000 | ≈540 h — exceeds the 720 h month once services need the GPU; not viable | ≈33 h; $0 | ≈$82.50 |

Qwen3.5-4B roughly halves column (a)/(a') times (≈300 t/s pp, ≈30 t/s tg, computed). The takeaway: **local is free but slow; it pays off only for many small jobs, not for 150k-token agent runs.** For comparison, the Claude Max subscription you already have is the right lane for the big jobs (see the Claude doc in this folder).

**Free tiers:** the whole stack is free. EmbeddingGemma requires accepting Google's Gemma license on Hugging Face [46] (the Ollama pull does not prompt [13]).

## 5. Strengths & weaknesses per reviews

**Benchmarks (vendor cards, self-reported):**

| Model | GPQA Diamond | MMLU-Pro | LiveCodeBench v6 | BFCL-V4 (tool use) | TAU2-Bench | SWE-bench Verified | Source |
|---|---|---|---|---|---|---|---|
| Qwen3.5-9B | 81.7 | 82.5 | 65.6 | 66.1 | 79.1 | — | [20] |
| Qwen3.5-4B | 76.2 | 79.1 | 55.8 | 50.3 | 79.9 | — | [28] |
| Gemma 4 12B | 78.8 | 77.2 | 72.0 | not on card | — | — | [29] |
| Gemma 4 E4B | 58.6 | 69.4 | 52.0 | not on card | — | — | [47] |
| Gemma 3 27B (prev gen, for scale) | 42.4 | 67.6 | 29.1 | — | — | — | [29] |
| gpt-oss-20b (medium) | 58.6 (71.5 per Qwen's table) | — | — | — | — | 53.2 (34.0 per GLM's table) | [30][20][33] |
| DeepSeek-R1-0528-Qwen3-8B | 61.1 | — | 60.5 (LCB) | — | — | — | [31] |
| GLM-4.7-Flash 30B-A3B | 75.2 | — | — | — | — | 59.2 | [33] |
| Phi-4-mini 3.8B | — | MMLU 67.3 | — | — | — | — | [32] |

Sources conflict on gpt-oss-20b: its own card says GPQA 58.59 and SWE-bench 53.2 [30]; Qwen's comparison table lists GPQA 71.5 [20] and GLM's lists SWE-bench 34.0 [33] — different reasoning-effort settings and harnesses. Treat cross-vendor tables as directional.

**Artificial Analysis Intelligence Index v4.3.2** (10 evals): in the 4B-40B "small" class the leaders are Qwen3.8 27B (34 at xhigh), Gemma 4 31B (19), Qwen3.6 35B-A3B (18) — all too large for this box [21]. In the ≤4B "tiny" class: K2 Horizon 3.7B 16, MiniCPM5-2B 12, G9v3-3B 11, Granite 4.2 3B 9, Nanbeige4.1-3B 8, Qwen3.5 2B 7 (reasoning) / 6, Phi-4-mini 6 [44]. Qwen3.5-4B/9B and Gemma 4 12B are not on the pages fetched (searched the small and tiny category pages). **Availability check on the tiny leaders (2026-09-24):** there is no `k2-horizon` model in Ollama's library (a search for "k2" returns only `kimi-k2.6` / `kimi-k2.7-code`, which are cloud-scale Moonshot models) [68]; MiniCPM5-2B exists only as community uploads (`openbmb/minicpm5-2b`, 2 weeks ago, ~7K pulls), not as an official library entry [69]; neither has been run here. Granite 4.2 3B *is* in the official library (2.2 GB, Apache 2.0, 128K, text-only, tool calling on the OpenAI function schema, BFCL-V4 52.41, MMLU-Pro 67.84 per card; 8B: BFCL-V4 52.39, MMLU-Pro 74.04, GPQA 64.14) [60][61][62] and outscores Qwen3.5 2B on the AA tiny index (9 vs 7) — it was not evaluated as a candidate in this pass and is the obvious next thing to A/B against `qwen3.5:4b` for text-only classification/extraction (see §7).

**Best at (community + benchmarks):**
- **Tool calling / structured extraction:** "Qwen family gets 100% tool calling across every framework tested. Non-Qwen models (Llama, DeepSeek-R1) vary wildly — 40% to 100%" — raullen, HN 2026-04, seven models × five agent frameworks (Rapid-MLX thread, objectID 47816238) [59]. "small models like the new qwen3.5:9b can be fantastic for local tool use, information extraction" — mark_l_watson, HN 2026-03 [27]. Fuzzy table extraction/OCR of data that cannot leave the machine — seemaze, HN 2026-04 [27].
- **Classification / routing:** a 16 GB M4 mini user runs "a small Qwen model for headline classification" at ~5.5 GB resident — busymom0, HN 2025-11 [24]. This is exactly the workload profile that fits.
- **Summarization, multilingual:** Qwen3.5 claims 201 languages [8], Gemma 4 140+ [47]; Llama 3.2 3B "outperforms Gemma 2 2.6B and Phi 3.5-mini on … summarization, prompt rewriting, and tool use" [36].
- **Vision on small models:** Qwen3.5-4B MMMU-Pro 66.3 [28] beats Qwen3-VL-30B (63.0 — comparison value unverified as of 2026-09-24; only the 66.3 was confirmed from the card); Gemma 4 12B accepts image + audio + video [29].

**Weak at:**
- **Agentic coding / repo exploration:** "30%-50% of the content it generated for a research task (local code repo exploration) turned out to be plain wrong to the extent of made up file names and function names" — flutetornado, HN 2026-03-13, on qwen3.5:9b (objectID 47371290; confirmed via the author-filtered query [64] — the quote no longer appears in the [27] result set). Gemma 4 12B "just starts confusing itself really quickly when I give it coding tasks" — sleepyeldrazi, HN 2026-06 [27]. A 16 GB M4-mini user retreated from 9B models to Qwen3.5-0.8B for coding-agent experiments — brainless, HN 2026-06 [24] (unverified as of 2026-09-24: not found via an author-filtered Algolia search, and the [24] result set now shows only busymom0 and Spooky23; the one brainless comment that *was* found (2026-09-02, objectID 49531294) says he runs Qwen3.5 4B and 9B on a 16 GB M4 mini with purpose-built per-task harnesses and uses Codex/Claude Code/opencode for the coding agents — consistent with "small models need a harness", not with a retreat to 0.8B).
- **Single-shot tool calling:** Ollama's docs mark the single-shot (one round-trip) recipe as "only recommended for models which only return a single tool call"; use the multi-turn loop with parallel tool calls otherwise [16].
- **Long context on this hardware:** KV math in §3; prompt processing at ~150-220 t/s means a 32K prompt costs 2.5-3.5 minutes before the first token (computed from [2]).
- **Reasoning-mode verbosity:** DeepSeek-R1-0528-Qwen3-8B averages ~23K thinking tokens per AIME question [31] — at 16 t/s that is 24 minutes; disable thinking (`think: false`) for anything latency-sensitive [50].

**Runtime reliability record:**
- Ollama's MLX backend (preview since ~2026-03-31 per yg1112 — comment date confirmed; the "preview" status comes from the story title, not the quoted comment (unverified as of 2026-09-24)) is mixed: Ollama maintainer Patrick_Devine calls MLX builds "considerably faster than the GGML based versions" (2026-04-16), but d4rkp4ttern measured the third-party oMLX server (not Ollama's MLX backend) generating 3-7x *slower* than llama.cpp Metal on an M1 Max with Gemma 4 26B-A4B (5-13 vs 40 t/s, 2026-04-06, in the 'Running Gemma 4 locally with LM Studio' thread) — an MLX-vs-GGML data point, not evidence about Ollama's runner, and gcr reported the MLX backend "doesn't work at all without segfaulting the server process" (2026-05-20) [42]. Ollama's changelog through v0.34.4 is still fixing MLX memory growth and handling [41] (unverified as of 2026-09-24: the v0.34.4 notes mention MLX prompt-processing speedups for Qwen3.8, Gemma 4 image-resolution selection and generic "improved memory handling"; a specific MLX memory-growth fix could not be confirmed). **Prefer the GGUF path for an unattended server today.**
- Speed claims for MLX-native servers: Rapid-MLX reports Qwen3.5-9B at 108 t/s vs ~41 t/s on Ollama on an M3 Ultra [59]; MetalRT claims 1.1-1.2x MLX and 1.6-1.7x llama.cpp on M4 Max [26]. These are Ultra/Max-class numbers and third-party projects; not verified on base M4.
- **Quantization quality loss (why Q4 is acceptable, not just memory-driven):** llama.cpp's reference perplexity table for a 7B model gives Q4_K_M +0.0535 ppl (3.80 GB), Q5_K_M +0.0142 (4.45 GB), Q6_K +0.0044 (5.15 GB), Q8_0 +0.0004 (6.70 GB) relative to F16 (13.0 GB); Q4_K_M/Q5_K_S/Q5_K_M are the "recommended" tiers [70]. That is a <1% perplexity penalty for halving memory versus q8_0, so the Q4 recommendation in §7 costs little on bounded tasks; the `-mlx` tags are ~8-bit-sized and buy ~0.05 ppl for +35% memory, which this box cannot spare. The table is 2023-era LLaMA data; no per-model Qwen3.5/Gemma 4 quant-quality measurement was found.
- Quantization confusion (Q4_K_M vs IQ4_XS vs UD-Q4_K_XL) is a recognized UX gap for 16 GB users — mingodad, HN 2026-03 [24]. Ollama's `-mlx` tags are ~8-bit-sized (9b-mlx 8.9 GB vs 6.6 GB Q4_K_M), the exact MLX quant is not labeled [40] — pulling `-mlx` by habit will blow the memory budget.

**Controversies:** gpt-oss ships only in MXFP4 with no other quants [57]; EmbeddingGemma and Gemma 3 use Google's Gemma license, Gemma 4 moved to Apache 2.0 [29][46][5]; DeepSeek distills require DeepSeek's config files, not Qwen's, or tokenization breaks [31].

## 6. Finance / trading relevance

- **Real-time data:** none — local models have no network access; every price, filing or headline comes through your tools. gpt-oss's "built-in browsing/python" listed on Ollama's page [3] is a tool-call convention the *host* must implement.
- **Market-data connectors:** none first-party. Atlas already has Alpaca/Tradier plumbing; a local model can be a `tools=[get_quote, get_positions]` consumer via Ollama's tool calling [16] with Qwen3.5 as the reliable caller [59].
- **Sentiment / classification:** the sweet spot. Headline/news classification on a 16 GB M4 mini is a documented working use [24]; EmbeddingGemma/Qwen3-Embedding give local vectors for dedup, clustering and retrieval over research notes [46][14].
- **Embedding throughput for news dedup/clustering:** not measured on this box. EmbeddingGemma is 300M parameters at 622 MB with a 2K window [13][46], i.e. ~10x fewer weights than the 4B chat model, and `/api/embed` takes a batched `input` list [58]; treat it as "headlines per second, not per minute" until the llama-bench run in §4 pins it down. Practical shape: embed each headline at `dimensions=256`, cosine-dedupe above a threshold you tune on a labeled week, cluster the remainder, then send one representative per cluster to the 4B classifier — so the LLM sees clusters, not the firehose. `qwen3-embedding:0.6b` (32K ctx) is the choice when the unit is a paragraph or filing section rather than a headline [14].
- **Long filings (10-K-sized inputs) and the KV cache:** a full 10-K is far past the 8K envelope in §3/§7 (dense-8B f16 KV ≈144 KB/token → 8K ≈1.15 GB; a 100K-token prompt would need ≈14 GB f16 / ≈7 GB q8_0 — computed, infeasible next to Postgres) and would take 8-11 min of prompt processing at 150-220 t/s (computed from [2]). The strategy is retrieve-then-extract, not read-the-whole-thing: chunk sections to ≤6K tokens, embed with `qwen3-embedding:0.6b`, pull the sections the question needs (Item 1A risk factors, Item 7 MD&A, the specific notes), and run schema-constrained extraction per chunk with `num_ctx` 8192, merging results in Python. Anything that needs the whole filing in one context is a Claude job.
- **Finance-specific products:** none in this ecosystem. Restrictions: none beyond model licenses (all permissive for commercial use [20][29][30][43][31][33]).
- **Caution for Atlas:** the hallucination reports above [27] apply to numeric reasoning too. Use local models to *label, route and summarize*, never to compute P&L, size positions or write theses unsupervised; Atlas's adversarial-review lanes should stay on Claude.

## 7. Integration recipe for our server

**Interface:** Ollama (GGUF/llama.cpp backend), installed via Homebrew and supervised by launchd, native REST on `127.0.0.1:11434` [48][17]. Keep llama-server as a fallback for grammar-constrained JSON when Ollama's schema enforcement misbehaves [22]. Skip mlx_lm.server (not production-grade [38]) and Ollama's MLX runner (stability record [42][41]) for now; revisit in one release cycle.

**Auth / cost path:** none / $0. No Anthropic key involved, consistent with the subscription-only policy.

**Models to pull (≈13 GB on disk, never all resident):**

```bash
brew install ollama && brew services start ollama                 # launchd service [48]
launchctl setenv OLLAMA_CONTEXT_LENGTH 8192                        # default is 4096 [17]
launchctl setenv OLLAMA_KV_CACHE_TYPE q8_0                          # halve KV memory, global [17]
launchctl setenv OLLAMA_MAX_LOADED_MODELS 1                         # one LLM at a time on 16 GB [17]
launchctl setenv OLLAMA_NUM_PARALLEL 1                              # KV scales with parallelism [17]
launchctl setenv OLLAMA_KEEP_ALIVE 10m                              # unload when idle [17]
brew services restart ollama
ollama pull qwen3.5:4b            # 3.4 GB  — default worker (routing/classify/extract) [8]
ollama pull qwen3.5:9b            # 6.6 GB  — quality tier for summaries/extraction [8]
ollama pull embeddinggemma        # 622 MB — 768-d, MRL 128/256/512, 2K ctx [13][46]
# optional: ollama pull gemma4:12b (7.6 GB) for image/audio inputs [9]
# candidate to A/B, not yet evaluated: ollama pull granite4.2:3b (2.2 GB, Apache 2.0, 128K, text-only) [60]
```

**Minimal Python (structured classification with a fallback to Claude):**

```python
import ollama                                    # official SDK; native /api/chat [49]
from pydantic import BaseModel

class Route(BaseModel):
    lane: str            # "research" | "coding" | "trading" | "chat"
    confidence: float
    needs_frontier: bool

def route(text: str) -> Route:
    r = ollama.chat(
        model="qwen3.5:4b",
        messages=[{"role": "system", "content": "Classify the job. Return JSON."},
                  {"role": "user", "content": text[:6000]}],
        format=Route.model_json_schema(),          # schema-constrained [15]
        think=False,                               # skip <think> for latency [50]
        options={"temperature": 0, "num_ctx": 8192, "num_predict": 200},
        keep_alive="10m",
    )
    out = Route.model_validate_json(r.message.content)
    tps = r.eval_count / (r.eval_duration / 1e9)   # telemetry to the audit log [49]
    return out

def embed(texts: list[str]) -> list[list[float]]:
    return ollama.embed(model="embeddinggemma", input=texts, dimensions=256).embeddings  # [58]
```

Memory guard before each local call (Python): read `vm_stat`/`psutil.virtual_memory().available`; if < 3 GB free, skip local and route to Claude. Ollama will otherwise swap the box and stall Postgres.

**Task classes it fits here:**
- **Classification / routing** (job lane, Telegram intent, news sentiment): yes — Qwen3.5-4B with schema; measured-class use on this exact hardware [24].
- **Extraction** (tickers, dates, fields from filings/emails): yes — Qwen3.5-9B, schema-constrained [15][27].
- **Summarization** of ≤8K-token inputs (audit logs, job outputs, digests): yes at 9B; chunk larger inputs.
- **Embeddings / dedup / retrieval:** yes — EmbeddingGemma (fast, 2K ctx) or `qwen3-embedding:0.6b` (639 MB, 32K ctx, 100+ languages) [13][14]; `bge-m3` (1.2 GB, 8K, dense+sparse) if hybrid retrieval is wanted [35]; `nomic-embed-text` (274 MB) is the older default [34].
- **Chat:** only as a fallback when Claude is rate-limited; 16 t/s is tolerable for Telegram replies.
- **Research, coding, code review, adversarial review, trading research:** no — route to Claude; local 9B models fabricate file/function names in repo exploration [27] and lose the thread on coding tasks [27].
- **Pre-filter before Claude:** the best ROI: local model drafts a triage/summary so the Claude job starts with a smaller prompt.
- **Open candidate:** `granite4.2:3b` (IBM, 2.2 GB, text-only, BFCL-V4 52.41 on its card, AA tiny index 9) was not evaluated here; A/B it against `qwen3.5:4b` on the routing schema above before assuming Qwen is the only answer [60][61][44].

**Apple Foundation Models framework — the zero-cost classifier alternative to `qwen3.5:4b` (evaluated 2026-09-24, not yet run):**

| Dimension | Apple on-device model (FoundationModels) | `qwen3.5:4b` via Ollama |
|---|---|---|
| Model | ~3B parameters, 2-bit QAT weights, 4-bit embeddings, 8-bit KV cache, KV-cache sharing; trained on sequences up to 65K but **served with a 4,096-token context per session** (instructions + prompts + outputs all count) [79][80][81] | 4B hybrid, Q4_K_M 3.4 GB, 256K context, 8K envelope here [8][28] |
| Availability | macOS 26.0+, Apple Intelligence enabled, model downloaded by the OS (≈3 GB per one HN report [87]); this box runs Darwin 25.6 = macOS 26.x, so it is eligible pending the Apple Intelligence toggle; check `SystemLanguageModel.default.availability` (`deviceNotEligible` / `modelNotReady`) before every call [77][78] | any macOS with Metal |
| Memory | system-managed: the OS owns the weights, so nothing is added to Ollama's wired-memory budget in §3 and there is no `keep_alive` eviction dance; **it is still the same 16 GB of unified memory**, so "no contention with Postgres" means no *allocator* contention, not free RAM — resident size is unmeasured (computed expectation: ≈1-1.5 GB for 3B at 2-bit + KV, unverified) | 3.4 GB weights + KV, wired by the Ollama process [3][17] |
| Structured output | `@Generable` guided generation with constrained decoding ("strong guarantees that the model generates instances of your type") [77][80] | `format=<JSON schema>` [15] |
| Tools / streaming / sessions | `Tool` protocol, `streamResponse`, `LanguageModelSession` transcript; `prewarm()`; `tokenCount(for:)` and `contextSize` for budgeting; **one request per session at a time** (`isResponding`) [77][78][79] | tools, NDJSON streaming, stateless replay [16][49] |
| What Apple says it is for | summarize, extract entities, classify or judge text, tag, refine — and explicitly **not** "basic math, create code, perform logical reasoning" [78] | same bounded set (§7 task classes) |
| Quality evidence | Apple's own human evals only: "performs favorably against the slightly larger Qwen-2.5-3B across all languages and is competitive against the larger Qwen-3-4B and Gemma-3-4B in English" [80] — i.e. roughly one generation behind Qwen3.5-4B; no third-party benchmark of the on-device model was found, and HN opinion is thin ("pretty good at certain tasks", an0malous 2025-12-08 [87]) | GPQA 76.2, MMLU-Pro 79.1, BFCL-V4 50.3 on the card [28] |
| Languages | 15 languages; locales listed de/en/es-419/fr/it/ja/ko/pt-BR/zh-CN [77][80] | 201 languages claimed [8] |
| Python / server access | none first-party (Swift only). Shims: **`afm`** (`brew install scouzi1966/afm/afm` or `pip install macafm`, v0.9.19, MIT; OpenAI-compatible `/v1/chat/completions` + `/v1/embeddings`, structured output, tool calling, Prometheus `/metrics`; README claims it runs "without rate limiting as a local daemon") [83]; **`apple-on-device-openai`** (SwiftUI app, MIT, 889 stars; `/v1/chat/completions` streaming) which documents the trap: "An app with UI running in foreground has no rate limit; a CLI tool does" [82] | official `ollama` SDK [49] |
| Cost | $0, no download managed by us, no account, no key | $0 |
| Customization | rank-32 LoRA adapters via Apple's Python toolkit; "must be retrained with each new version of the base model" [80] | fine-tunes are third-party |

**Verdict on the alternative:** worth a real A/B as the *default classifier* for inputs that fit in ≈3K tokens (Telegram intent, job-lane routing, headline sentiment, tag generation), because it costs nothing, is not evicted when Ollama swaps models, and has first-class constrained decoding. It is **not** a replacement for `qwen3.5:9b` extraction/summarization: the 4,096-token session cap (vs. the 8K envelope) forces chunk-and-merge for anything longer, Apple's own guidance excludes reasoning and code, and quality sits a generation behind Qwen3.5. Three things must be verified on the box before it enters the router, all currently unknown: (1) whether a launchd-supervised `afm` daemon is throttled the way CLI callers reportedly are [82][83]; (2) resident memory and TTFT/t/s with Postgres up (same bench discipline as §4); (3) the Foundation Models acceptable-use terms — Apple's "acceptable use requirements" page returned 404 on 2026-09-24, so whether outputs may be served to non-owner users (pickem, project sites) through a shim is **unverified**. Pipeline shape if it passes: Apple model → JSON label (≤3K tokens) → `qwen3.5:9b` only when `needs_frontier`/long-input → Claude. Recommended first probe:

```bash
pip install macafm && afm serve &                                   # OpenAI-compatible on localhost [83]
curl -s localhost:<port>/v1/chat/completions -d '{"model":"apple","messages":[{"role":"user","content":"Classify: ..."}],"response_format":{"type":"json_schema","json_schema":{...}}}'
curl -s localhost:<port>/metrics | grep -E 'afm:.*(ttft|tokens)'    # Prometheus timing/throughput [83]
```

**Gotchas:**
1. Metal wires ~2/3 of RAM by default (~10.7 GB) [52]; raising `iogpu.wired_limit_mb` on a 16 GB box starves Postgres — do not.
2. `num_ctx` defaults to 4096 [17]; long prompts silently truncate. Set it per request; each doubling doubles KV.
3. `-mlx` tags are ~8-bit-sized (qwen3.5:9b-mlx 8.9 GB) [40]; never pull them here.
4. Qwen3.5 thinks by default [28]; pass `think=False` or budget 2-10x more output tokens [50].
5. Ollama OpenAI-compat lacks `tool_choice` and logprobs [7], and the Anthropic-compat `/v1/messages` lacks `tool_choice`, prompt caching, Batches and PDF blocks [75]; to force a tool, use schema output instead.
5a. Apple Foundation Models: 4,096-token session cap (`contextSizeExceeded`), one in-flight request per session, and a reported throttle for non-foreground/CLI callers — measure from launchd before trusting it [78][79][82].
6. `OLLAMA_KV_CACHE_TYPE` is global [17]; embedding models are unaffected, but all chat models drop to q8 KV.
7. gpt-oss-20b needs the harmony format and MXFP4 only [30][57]; it fits a bare 16 GB Mac (11-13 GB [23]) but not this one with services up.
8. Model pages disagree on context (Ollama lists nomic-embed-text at 2K [34]; the underlying model is advertised as long-context — verify with `/api/show` before relying on >2K inputs).
9. The Apple spec page now lists only M6/M5 Pro Mac minis [18]; M4 base figures in this doc come from llama.cpp's benchmark table (10 GPU cores, 120 GB/s) [2].

## 8. Verdict

1. On a 16 GB M4 mini sharing memory with Postgres/Redis/runner, the workable envelope is one ≤7 GB Q4 model at ≤8K context: **Qwen3.5-4B** (default) and **Qwen3.5-9B** (quality), plus **EmbeddingGemma** [8][13][52].
2. Expect ~16-35 t/s generation and ~150-300 t/s prompt processing on the base M4; every fast number online is a Pro/Max/Ultra [2][56].
3. Use it for classification, routing, extraction, summarization and embeddings with schema-constrained output; Qwen is the reliable tool-caller in the class [15][59].
4. Do not use it for agentic coding, research or adversarial review — 9B-class models hallucinate repo structure at 30-50% rates in reviewers' hands [64]; keep those on the Claude Max lane.
5. gpt-oss-20b, Gemma 4 26B/31B, Qwen3.6/3.8 (smallest tag 18 GB; the new Qwen3.8-Flash-Next is also no longer Apache 2.0), Muse Glimmer 30B, Granite 4.2 30B, DeepSeek-V4.x and GLM-5.x are out of envelope on this box; the MLX runtimes are faster on paper but Ollama's MLX backend is not yet stable enough for an unattended server [23][42][41].

6. First action before any integration work: the 10-minute `llama-bench` / `ollama run --verbose` measurement in §4 — every throughput and memory figure in this doc is computed or borrowed, none is from this machine (re-confirmed 2026-09-24: no base-M4 16 GB Qwen3.5 figures exist on the public web either [90]).
7. Ollama's `/v1/messages` Anthropic-compatible endpoint means the existing Claude Code / Agent SDK dispatch can target a local model by env var for bounded sub-jobs [75][76]; and Apple's on-device Foundation Model is a credible $0 classifier for ≤3K-token inputs that should be A/B'd against `qwen3.5:4b` before the router is designed, subject to the three unknowns in §7 [78][80][82][83].

**Cross-doc router dimensions (local lane, filled 2026-09-24 so the crosscut matrix has a row):**

| Dimension | Local (Ollama / llama.cpp GGUF) | Apple Foundation Models | Ollama Cloud (escape hatch, not recommended) |
|---|---|---|---|
| **Data handling** (training use / retention / residency / ZDR) | nothing leaves the box; no training use, retention = your disk and audit log, residency = the mini; ZDR is the default state, not a tier. Proprietary theses can be routed here without a contract [7][37] | on-device model: same as local. **Caveat:** the framework overview also lists "Private Cloud Compute models"; select only `SystemLanguageModel` if residency matters [77] | "We do not use them to train models"; retention window and residency **not stated**; per-account API key; outside policy without an owner decision [72] |
| **Progress visibility** (quota introspection / telemetry export) | no quota concept to introspect. Per-call `eval_count`, `eval_duration`, `prompt_eval_count`, `total_duration` in every response [49]; `GET /api/ps` gives `size`, `size_vram`, `context_length`, `expires_at` per loaded model [88]; `llama-server` and `afm` expose Prometheus metrics [22][83]. **Best-instrumented lane in the set** — the audit log can carry t/s per job today | `afm` `/metrics` (Prometheus `afm:*`, vLLM-compatible queue/token/timing) [83]; nothing first-party | credits balance only via account UI (unverified) [37] |
| **Third-party serving** (may non-owner users consume outputs: pickem, project sites) | runtimes: Ollama and llama.cpp are MIT — no restriction. **LM Studio terms (2026-08-23): "personal and/or internal business purposes" only; prohibited "service bureau use, as an application service provider, or a software-as-a-service"** — LM Studio cannot sit behind a shared site [84]. Model weights: Apache 2.0 (Qwen3.5, Gemma 4, gpt-oss, Ministral 3, Granite 4.2) unrestricted [20][29][30][43][61]; Gemma terms (Gemma 3, EmbeddingGemma) treat "a hosted service via API, web access" as Distribution and require passing through the use restrictions + Prohibited Use Policy — allowed, with the notice obligation [91]; Llama 3.2 license page sits behind a Meta login wall as of 2026-09-24 (unverified; do not use `llama3.2` behind shared surfaces until read) | serving end-users is the framework's design intent, but the acceptable-use page 404'd — **unverified** (§7) | Ollama ToS not fetched — unverified |
| **Reliability** (incidents / status page / SLA-priority tiers) | no vendor, no status page, no SLA; reliability = this box + runtime bugs. Known runtime incidents in the record: Ollama MLX backend segfaults (gcr, 2026-05-20) [42]; GGUF path has no reported crash class. Incident count over any window: 0 external, internal unknown until the audit log records local-call failures | Apple ships it with the OS; availability states (`modelNotReady`, `deviceNotEligible`) are the failure modes to log [78] | `status.ollama.com` does not resolve (DNS, 2026-09-24) — no status page found; no priority/SLA tier on the pricing page [37] |
| **Interactive latency** (Telegram round trip) | TTFT = cold load (6.6 GB from SSD, seconds to tens of seconds, unmeasured) + prompt processing at ~150-300 t/s computed [2] → ≈3-7 s for a 1K-token chat context, ≈30-50 s for 8K; then 16-35 t/s streaming. **Rating for the chat surface: acceptable only with the model pinned (`keep_alive: -1`) and ≤2K context; otherwise Claude** | `prewarm()` exists; TTFT/t/s unmeasured; 4K context caps the transcript, which is fine for Telegram intent, not for long threads [79] | network + cloud-class model; TTFT unmeasured |
| **Tool churn** (release cadence / breaking-change rate) | Ollama: 4 releases in 10 days (v0.34.1 09-14 → v0.34.4 09-23), no "breaking" in those bodies; native `/api` and `/v1` shapes unchanged, but **model tags move under you** (a default tag can be re-pointed to a new quant/model) — pin by digest [85][40]. llama.cpp: 2 tagged builds on 2026-09-24 alone (b11159, b11160), every build marked prerelease — pin the Homebrew formula version [86][54]. Burden: **medium** (weekly minor releases, low API churn, high model-tag churn) | Apple: OS-cadence (annual major, point releases); adapters "must be retrained with each new version of the base model" [80]; shims are pre-1.0 (`afm` v0.9.19) — burden **low for the API, high for anything fine-tuned** [82][83] | model roster changes weekly (19 cloud models on 09-24) [71] |

**Fit scores, calibrated (1-10; anchors so the crosscut can normalize: research 10 = frontier model with live web tools; coding/agentic 10 = Claude Code on the Max lane; cost 10 = $0 marginal per job; automation 10 = headless + no auth + schema output + per-call telemetry; trading research 10 = live data connectors + long-context reasoning):** local Ollama/GGUF — research **2** · coding/agentic **2** · cost **9** (free, slow) · automation **8** (launchd, REST, schema, telemetry; loses points for the memory guard and model-tag churn) · trading research **3** (labeling/sentiment only, no reasoning). Apple Foundation Models — research **1** · coding/agentic **1** · cost **10** · automation **6** (Swift-only first-party, shim-dependent, CLI throttle unverified) · trading research **2**. The previous uncalibrated line (research 3 / trading 4) is superseded; the change is anchor drift, not new evidence.

## 9. Sources

All accessed 2026-09-24.

1. https://ollama.com/library — Ollama model library index (families, sizes, recency)
2. https://github.com/ggml-org/llama.cpp/discussions/4167 — llama.cpp Apple Silicon performance table (M4: 10 GPU cores, 120 GB/s; 7B Q4_0 221 pp / 24.1 tg)
3. https://ollama.com/library/gpt-oss — gpt-oss 20b/120b sizes, 128K ctx, MXFP4, Apache 2.0
4. https://ollama.com/library/qwen3 — Qwen3 tags and sizes
5. https://ollama.com/library/gemma3 — Gemma 3 tags, QAT variants
6. https://github.com/ml-explore/mlx-lm — mlx-lm features, prompt caching, macOS 15 wired memory note
7. https://docs.ollama.com/api/openai-compatibility — OpenAI-compatible endpoints, supported/unsupported features
8. https://ollama.com/library/qwen3.5 — Qwen3.5 tags, sizes, 256K ctx, MLX tags, 201 languages
9. https://ollama.com/library/gemma4 — Gemma 4 tags, sizes, MoE 26B-A4B, sampling
10. https://ollama.com/library/ministral-3 — Ministral 3 tags, 256K ctx, Apache 2.0
11. https://ollama.com/library/phi4-mini — Phi-4-mini 3.8B, 2.5 GB, 128K, function calling
12. https://ollama.com/library/deepseek-r1 — R1 distill sizes and base models, MIT
13. https://ollama.com/library/embeddinggemma — 300M, 622 MB, 2K ctx
14. https://ollama.com/library/qwen3-embedding — 0.6b/4b/8b sizes, dims up to 4096, MTEB 70.58 (8B)
15. https://docs.ollama.com/capabilities/structured-outputs — `format` JSON schema, Pydantic, temperature 0, cloud unsupported
16. https://docs.ollama.com/capabilities/tool-calling — tools, streaming caveat, parallel tool calls
17. https://docs.ollama.com/faq — keep_alive, OLLAMA_MAX_LOADED_MODELS, NUM_PARALLEL, CONTEXT_LENGTH 4096 default, KV_CACHE_TYPE, launchctl setenv
18. https://www.apple.com/mac-mini/specs/ — current Mac mini lineup (M6 / M5 Pro; M4 no longer listed)
19. https://lmstudio.ai/docs/cli — `lms` server/load/unload commands, MIT
20. https://huggingface.co/Qwen/Qwen3.5-9B — architecture, 262,144 ctx, GPQA 81.7, BFCL-V4 66.1, TAU2 79.1, Apache 2.0, Feb 2026
21. https://artificialanalysis.ai/models/open-source/small — Intelligence Index v4.3.2 small-model scores and hosted prices
22. https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md — llama-server flags (--json-schema, --grammar, --jinja, -np, -ctk/-ctv, -fa)
23. https://hn.algolia.com/api/v1/search?query=gpt-oss-20b%2016GB%20mac&tags=comment — HN reports: gpt-oss-20b ≈11-13 GB resident on 16 GB Macs (simonw, lostmsu, vinhnx)
24. https://hn.algolia.com/api/v1/search?query=mac%20mini%20m4%2016gb%20ollama&tags=comment — HN: 16 GB M4 mini users (busymom0, mingodad, brainless, Spooky23)
25. https://hn.algolia.com/api/v1/search?query=iogpu.wired_limit_mb — HN on sysctl override risks (ljosifov, pixelesque)
26. https://hn.algolia.com/api/v1/search?query=mlx%20llama.cpp%20faster%20apple%20silicon&tags=comment — HN: MetalRT/vMLX speed claims, bandwidth-bound note
27. https://hn.algolia.com/api/v1/search?query=qwen3.5%209b%20local&tags=comment — HN opinions on Qwen3.5-9B vs Gemma 4 (mark_l_watson, seemaze, big_babol, sleepyeldrazi, flutetornado, aegis_camera)
28. https://huggingface.co/Qwen/Qwen3.5-4B — hybrid architecture (3 DeltaNet : 1 attention), benchmarks, sampling, thinking default
29. https://huggingface.co/google/gemma-4-12b-it — 11.95B, 256K, Jan-2025 cutoff, Apache 2.0, benchmarks, family list
30. https://huggingface.co/openai/gpt-oss-20b — 21B/3.6B active, 16 GB claim, harmony format, GPQA 58.59, SWE-bench 53.2
31. https://huggingface.co/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B — benchmarks vs Qwen3-8B, MIT, ~23K thinking tokens/question
32. https://huggingface.co/microsoft/Phi-4-mini-instruct — 3.8B, 128K, June-2024 cutoff, MIT, benchmarks
33. https://huggingface.co/zai-org/GLM-4.7-Flash — 30B-A3B, 131K, MIT, benchmarks vs gpt-oss-20b
34. https://ollama.com/library/nomic-embed-text — 274 MB, 2K ctx (as listed)
35. https://ollama.com/library/bge-m3 — 1.2 GB, 8K ctx, dense/sparse/multi-vector
36. https://ollama.com/library/llama3.2 — 1b/3b sizes, 128K ctx, claims vs Gemma 2 / Phi 3.5
37. https://ollama.com/pricing — Free / Pro $20 / Max $100 / Team $500 tiers; local unlimited
38. https://raw.githubusercontent.com/ml-explore/mlx-lm/main/mlx_lm/SERVER.md — mlx_lm.server port 8080, not for production
39. https://lmstudio.ai/docs/app/api/headless — llmster daemon, headless app, JIT loading
40. https://ollama.com/library/qwen3.5/tags — per-tag quantization and sizes (q4_K_M default; -mlx sizes)
41. https://github.com/ollama/ollama/releases — v0.34.4 (2026-09-23), MLX fixes, single-pass structured outputs
42. https://hn.algolia.com/api/v1/search?query=ollama%20mlx%20backend&tags=comment — HN on Ollama MLX backend (yg1112, Patrick_Devine, gcr); d4rkp4ttern's 3-7x figure is a separate comment about oMLX (author-filtered query: https://hn.algolia.com/api/v1/search?query=oMLX%20llama.cpp&tags=comment,author_d4rkp4ttern)
43. https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512 — 8.4B + 0.4B vision, 256K, Apache 2.0, Dec 2025, benchmarks
44. https://artificialanalysis.ai/models/open-source/tiny — Intelligence Index v4.3.2 tiny-model scores
45. https://hn.algolia.com/api/v1/search?query=recommendedMaxWorkingSetSize — HN: ~66% of RAM usable by GPU on 32 GB (indexerror)
46. https://huggingface.co/google/embeddinggemma-300m — 768-d, MRL 512/256/128, 2048 ctx, MTEB v2 multilingual 61.15, Gemma license
47. https://huggingface.co/google/gemma-4-e4b-it — 4.5B effective / 8B total, 128K, benchmarks, Apache 2.0, native tool support
48. https://formulae.brew.sh/formula/ollama — 0.34.4, `brew services start ollama`, MIT
49. https://docs.ollama.com/api/chat — /api/chat fields, NDJSON streaming, eval_count/eval_duration
50. https://docs.ollama.com/capabilities/thinking — `think` true/false/low/medium/high, message.thinking
51. https://ollama.com/blog/structured-outputs — schema-constrained outputs, best practices
52. https://github.com/ggml-org/llama.cpp/discussions/2182 — Metal reserves 33.3% of RAM (≤32 GB) / 25% (>32 GB); sysctl iogpu.wired_limit_mb; swap-thrash warning
53. https://huggingface.co/Qwen/Qwen3-8B — 8.2B, 32K native / 131K YaRN, GQA 8 KV heads, Qwen-Agent MCP
54. https://formulae.brew.sh/formula/llama.cpp — 0.5.0, llama-server/llama-bench, MIT
55. https://lmstudio.ai/blog/lmstudio-v0.3.4 — MLX engine (mlx-lm + Outlines + mlx-vlm), KV-cache re-prompt 10 s → 0.11 s
56. https://hn.algolia.com/api/v1/search?query=%22tok%2Fs%22%20m4%20qwen3&tags=comment — HN tok/s reports on M4 family (Analemma_, ionwake, isomorphic, argee, mswphd, asats, c16)
57. https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama — ≥16 GB VRAM/unified memory, ollama commands, MXFP4 only, no native Responses API in Ollama
58. https://docs.ollama.com/api/embed — /api/embed fields incl. `dimensions`, `truncate`
59. https://news.ycombinator.com/item?id=47816238 — Rapid-MLX thread; raullen's 7-model × 5-framework tool-calling benchmark (Qwen 100%), Qwen3.5-9B 108 t/s vs 41 on Ollama (M3 Ultra)
60. https://ollama.com/library/granite4.2 and https://ollama.com/library/granite4.2/tags — Granite 4.2 3b 2.2 GB / 8b 5.3 GB / 30b 18 GB, 128K, text, Apache 2.0, "3 weeks ago"; per-quant tag sizes
61. https://huggingface.co/ibm-granite/granite-4.2-3b — dense decoder-only GQA (40 Q / 8 KV heads), 128K native / 512K extension, 12 languages, released 2026-08-25, Apache 2.0, MMLU-Pro 67.84, BFCL-V4 52.41, tool calling on OpenAI function schema
62. https://huggingface.co/ibm-granite/granite-4.2-8b — 8B dense, MMLU-Pro 74.04, BFCL-V4 52.39, GPQA 64.14, IFBench 79.33, Apache 2.0
63. https://ollama.com/library/qwen3.8/tags — all 12 qwen3.8 tags are 27b (18 GB Q4_K_M/MLX/NVFP4 up to 56 GB BF16); no sub-27B tag
64. https://hn.algolia.com/api/v1/search?query=qwen3.5&tags=comment,author_flutetornado — flutetornado's 30-50% hallucination comment on qwen3.5 9b (2026-03-13, objectID 47371290, "Can I run AI locally?")
65. https://ollama.com/library/qwen3.8-flash-next — 125B total / 6B active MoE, 512 experts, 256K (1M YaRN), text+image, `125b-mlx` 105 GB, Qwen Community License 1.0, "experimental preview of the architecture that will underpin Qwen4", 2 weeks ago
66. https://ollama.com/library/muse-glimmer — Meta Muse Glimmer 30B, Apache 2.0, 128K, text+image, tools+thinking, 18 GB (`30b`) / 19 GB (`30b-mlx`), 3 weeks ago
67. https://ollama.com/library/deepseek-v4.1-flash — 552B-backbone MoE (8B active prefill / 16B decode), 1M ctx, `:cloud` tag only, 2 weeks ago
68. https://ollama.com/search?q=k2 — no `k2-horizon`; only `kimi-k2.6` / `kimi-k2.7-code` match
69. https://ollama.com/search?q=minicpm — MiniCPM5-2B present only as community uploads (`openbmb/minicpm5-2b`, 2 weeks ago); official library has minicpm-v4.5/4.6 vision only
70. https://github.com/ggml-org/llama.cpp/discussions/2094 — k-quant perplexity table (7B: Q4_K_M +0.0535, Q5_K_M +0.0142, Q6_K +0.0044, Q8_0 +0.0004 vs F16)
71. https://ollama.com/search?c=cloud — 19 cloud models (gemma4, qwen3.5, gpt-oss, nemotron-3, glm-5.x, deepseek-v4.x, kimi, minimax, mistral-large-3)
72. https://docs.ollama.com/cloud — cloud auth via `OLLAMA_API_KEY` or app sign-in; "We do not use them to train models"; cloud features can be disabled
73. https://support.apple.com/en-us/103253 — Mac mini power consumption and thermal output: M4 idle 4 W / max 65 W (14 / 222 BTU/h); M4 Pro 5 W / 140 W
74. https://hn.algolia.com/api/v1/items/49531294 — brainless (2026-09-02): runs Qwen3.5 4B/9B experiments on a 16 GB M4 Mac mini with per-task harnesses; no mention of 0.8B
75. https://docs.ollama.com/api/anthropic-compatibility — `/v1/messages` (local and cloud); supported: messages, streaming, system, multi-turn, vision, tools, tool results, thinking; unsupported: `tool_choice`, `metadata`, prompt caching, Batches, PDF blocks; `ANTHROPIC_AUTH_TOKEN=ollama`, `ANTHROPIC_BASE_URL=http://localhost:11434`
76. https://docs.ollama.com/integrations/claude-code — `ollama launch claude`; manual env vars incl. empty `ANTHROPIC_API_KEY`; `claude --model <tag>`; ≥64K context advice; "tool-calling support varies"
77. https://developer.apple.com/tutorials/data/documentation/foundationmodels.json — Foundation Models framework overview (macOS 26.0+, `SystemLanguageModel`, `@Generable` guided generation, `Tool`, `LanguageModelSession`, dynamic profiles, image attachments, on-device and Private Cloud Compute models, supported locales)
78. https://developer.apple.com/tutorials/data/documentation/foundationmodels/generating-content-and-performing-tasks-with-foundation-models.json — "the system model supports up to 4,096 tokens"; `contextSizeExceeded`; availability states; suitable vs unsuitable tasks ("Do basic math / Create code / Perform logical reasoning"); one request per session (`isResponding`)
79. https://developer.apple.com/tutorials/data/documentation/foundationmodels/managing-the-context-window.json — 4096-token context per session, `contextSize`, `tokenCount(for:)`, transcript condensing, `prewarm()`
80. https://machinelearning.apple.com/research/apple-foundation-models-2025-updates — ~3B on-device model, 2-bpw QAT, 4-bit embeddings, 8-bit KV, trained to 65K sequences, 15 languages, rank-32 adapter toolkit (retrain per base version), human evals vs Qwen-2.5-3B / Qwen-3-4B / Gemma-3-4B
81. https://arxiv.org/abs/2507.13575 — Apple Intelligence Foundation Language Models Tech Report 2025 (3B on-device, KV-cache sharing, 2-bit QAT, tool calling, guided generation)
82. https://github.com/gety-ai/apple-on-device-openai — OpenAI-compatible SwiftUI server over Foundation Models; macOS 26+; MIT; 889 stars; "An app with UI running in foreground has no rate limit; a CLI tool does"
83. https://github.com/scouzi1966/maclocal-api — `afm` v0.9.19 (MIT): Apple Foundation Models + MLX runtimes behind `/v1/chat/completions`, `/v1/embeddings`, structured output, tool calling, Prometheus `/metrics`; `brew install scouzi1966/afm/afm` / `pip install macafm`; macOS 26+
84. https://lmstudio.ai/terms — LM Studio Terms (2026-08-23): "personal and / or internal business purposes"; no "service bureau use, as an application service provider, or a software-as-a-service"
85. https://api.github.com/repos/ollama/ollama/releases?per_page=40 — v0.34.1 (2026-09-14), v0.34.2 (09-15), v0.34.3 (09-19), v0.34.4 (09-23); no "breaking"/"Anthropic" in bodies
86. https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=40 — b11159 and b11160 both published 2026-09-24, marked prerelease
87. https://hn.algolia.com/api/v1/search?query=%22FoundationModels%22%20apple&tags=comment — HN on Apple FoundationModels (an0malous 2025-12-08 "pretty good at certain tasks"; coevcan 2026-05-11 ≈3 GB model download; hbcondo714 2025-06-20 `maximumResponseTokens` ignored; trollbridge 2026-04-03 macOS 26+)
88. https://docs.ollama.com/api/ps — `/api/ps` fields: `size`, `size_vram`, `expires_at`, `context_length`, `details.quantization_level`
89. https://docs.ollama.com/cli — `ollama launch` targets Claude Code, OpenCode, Codex, VS Code, Droid
90. https://hn.algolia.com/api/v1/search?query=%22base%20M4%22%20tok&tags=comment and https://hn.algolia.com/api/v1/search?query=qwen3.5%204b%20m4%20tok%2Fs&tags=comment — no base-M4 16 GB Qwen3.5 t/s figures (nozzlegear 2026-08-03 is an Air offloading to an M1 Ultra; sanchitmonga22 2026-03-11 is M4 Max; mingodad 2026-03-08 / brainless 2026-09-02 give no t/s)
91. https://ai.google.dev/gemma/terms — Distribution includes "a hosted service via API, web access"; use restrictions must be passed through; Prohibited Use Policy incorporated

## Verification log (2026-09-24)

**Corrections applied: 7** — 1 major (d4rkp4ttern's 3-7x slowdown was oMLX vs llama-server, not Ollama's MLX backend; §5 runtime record and source [42]), 6 minor (Gemma 4 arXiv id/date; Ollama tool-calling docs quoted precisely in §2 and §5; `think` levels are model-specific; `qwen3:4b` 256K applies to the 2507 tag only; [42] attribution).

**Claims re-verified with sources (this pass):**
- Granite 4.2 3B/8B/30B sizes, license, context, recency — [60]; card facts and benchmarks — [61][62].
- No `k2-horizon` on Ollama; MiniCPM5-2B community-only — [68][69]; AA tiny index rows (K2 Horizon 16, MiniCPM5-2B 12, Granite 4.2 3B 9, Qwen3.5 2B 7/6) — [44].
- Muse Glimmer 30B on Ollama (Apache 2.0, 18/19 GB, 128K) — [66]; Qwen3.8-Flash-Next 125B-A6B under Qwen Community License 1.0 — [65]; DeepSeek-V4.1-Flash cloud-only — [67]; smallest `qwen3.8` tag is 27b at 18 GB — [63].
- Quant perplexity deltas (Q4_K_M +0.0535 … Q8_0 +0.0004, 7B) — [70].
- Ollama Cloud model list, auth model, data-handling statement — [71][72].
- M4 Mac mini 4 W idle / 65 W max — [73].
- flutetornado 30-50% quote (2026-03-13, qwen3.5:9b, objectID 47371290) — [64]; d4rkp4ttern oMLX comment (2026-04-06, objectID 47668849) — author-filtered query in [42].
- `qwen3.5:2b` / `0.8b` default tags are q8_0 — [40].
- brainless's actual 16 GB M4-mini comment (2026-09-02) — [74].

**Stale / unverified flags left in place (marked "(unverified as of 2026-09-24)" in the text):** brainless "retreat to 0.8B" (contradicted by the only comment found); "MLX memory-growth" fixes in the v0.34.4 changelog; yg1112 "preview" status; Qwen3-VL-30B MMMU-Pro 63.0 comparison value; GLM-4.7-Flash 131K context; Qwen3.5-9B card boilerplate vs dense config (note added in table); hosted price for 4-9B open models; gpt-oss-20b knowledge cutoff; nomic-embed-text context (gotcha 8). Still unmeasured on this machine: every throughput/memory figure in §4 and the embedding throughput in §6 (the bench recipe in §4 is the fix).

**Gap-fix pass (2026-09-24, second pass):** (1) **Major correction** — §2 previously said no Anthropic-compatible endpoint exists; Ollama documents `/v1/messages` with Claude Code env-var setup [75][76]. (2) Added the Apple Foundation Models evaluation (§7) from Apple's docs and 2025 model report [77]-[81] plus the two OpenAI-compatible shims [82][83]; the acceptable-use page 404'd, so serving terms remain unverified. (3) Added the cross-doc router dimensions and calibrated fit scores (§8). (4) Re-confirmed that no base-M4 16 GB Qwen3.5 throughput exists on the public web [90]; the llama-bench run is still the prerequisite. Unfetchable this pass: Llama 3.2 license (Meta login wall), `status.ollama.com` (DNS), Apple acceptable-use page (404). Web search budget was exhausted; all facts come from directly fetched pages.

**Fact-checker's overall quality rating:** good.
