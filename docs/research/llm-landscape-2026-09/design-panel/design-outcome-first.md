# Design: Outcome-first — definitions of done, evidence, cross-vendor grading, measured routing

Architect lens: **deliverable effectiveness**. Date 2026-09-24. Inputs: `scratchpad/current-state-map.md` (state map; `file:line` cites below are from it and were spot-verified on 2026-09-24), `docs/research/llm-landscape-2026-09/*` (cited as `<doc> §n`), `docs/superpowers/plans/2026-08-10-model-router.md` (cited as `plan §n`).

## 0) Thesis

The server already owns a vendor-neutral lifecycle (job row + `jobs:queue`, per-job JSONL audit, text-marker final-text contract, fail-closed workspace clone: state map §6 "load-bearing" rows) but it has **no notion of what "done" means and no record of whether anything was done well**: `user_rating` on 2/1633 jobs, the INV-13 in-session `code-review` verdict is never stored, `post_review` has flagged 2 jobs ever, `evals/results/` is empty, `retrospective.skill_performance` has zero callers, and review-and-improve groups by `kind` so routed skills never appear (state map §2.5, §5 items 19–23). Every LLM call is one vendor grading itself (`review.py:250` hardcodes `claude-opus-4-7`; `evals/run.py:48` `JUDGE_MODEL`). Adding vendors on top of that would only multiply unmeasured output. So this design puts a **Deliverable Contract** (definition-of-done + evidence manifest) on every job, makes the runner — not the model — verify the mechanical checks, has a **different vendor grade the writer's work** (Anthropic stays the only vendor that can issue the INV-13 LGTM; cross-vendor graders are additive dissent, never the gate), records every verdict structurally, and builds a **provider scoreboard** (DoD pass-rate, grade, independence, cost, latency per task class) that drives routing through a shadow→canary→qualified ladder. Execution and surface changes are derived from that and kept minimal: extract the executor seam the state map already identified, add four tables and one migration, a grader post-step, per-provider quota, a persisted job→origin binding, and three views (watch, done, providers) on Telegram, web and a CLI. Everything is additive behind flags; the current Anthropic-only path remains the kill-switch state.

## 1) Architecture

### 1.1 Components

```
 Telegram ──┐                                            Executor registry (providers.yml)
 Web app ───┤  enqueue_job(job + contract)               ┌ anthropic/claude-sdk  writer · anchor gate · governor
 owner CLI ─┼──────────► jobs:queue (priority lanes) ───►│ codex/cli (ChatGPT)   grader · code-project canary
 Scheduler ─┤                 │                          │ gemini/http (unpaid)  grader(public-only) · utility
 Events ────┘                 ▼                          │ local/ollama          utility · mechanical checks
                       run_session(job)                  └ openrouter/http :free utility middle link
                              │  ExecSpec → adapter → normalized events
                              ▼
                 JSONL audit (truth) + jobs:stream + jobs:progress hash + job_events (PG projection)
                              │
              ┌───────────────┼──────────────────────┐
              ▼               ▼                      ▼
   evidence checks     grader stage           merge-gate verdict
   (deterministic,     (vendor ≠ writer,      (Anthropic in-session code-review,
    no LLM)             read-only, sandboxed)  INV-13; now recorded, pre-push)
              └───────────────┼──────────────────────┘
                              ▼
                        verdicts table ──► provider_ledger ──► scoreboard (view)
                                                                 │
                                          routing-policy.yml + qualification ladder ◄┘
                              │
                        notify.py ─► Telegram cards · web SSE · CLI · deliverables feed
```

| Component | New / changed | Where | Notes |
|---|---|---|---|
| **Deliverable Contract** | new | `src/contracts/{schema,checks}.py`; frontmatter `done:` block; payload `contract` | Declared per skill, overridable per job; §3.1 |
| **Executor protocol** | new seam, behavior-identical extraction | `src/runner/executors/{base,claude_sdk,codex_cli,http,script}.py` | `main.py:376-380` stays the single call site; `_run_in_process` (`session.py:1048-1132`) becomes `ClaudeSdkExecutor`; `_build_options` (`session.py:650-816`) split into `ExecSpec` + adapter at the five seams the map names (prompt 664-692, resolution 694-724, subagents 730-736, guards 752-755, MCP 757-796) |
| **Provider registry + policy** | new | `providers.yml`, `routing-policy.yml`, `src/providers/{registry,policy,quota}.py` | plan §6a/§6d shape; replaces the accidental allowlist in `telegram_bot.py:122-134` / `tests/test_skill_contracts.py:24` / `web.py:689-691` |
| **Grader stage** | new post-step | `src/runner/grading.py`, wired after `_maybe_review` in `main.py:381-444` | Runs evidence checks (no LLM) then an LLM grader on a different vendor; §3.2–3.3 |
| **Verdict ledger** | new tables | migration 007: `verdicts`, `provider_ledger`, `job_events`, `provider_qualifications`; columns on `jobs` | §1.2 |
| **Scoreboard** | new SQL view + rollup | `src/runner/scoreboard.py`; `GET /api/scoreboard`; `/scoreboard` | Replaces the uncalled `retrospective.skill_performance` (`retrospective.py:39`) |
| **Progress record** | new | Redis hash `jobs:progress:<id>` written by the executor adapter; consumed by `/watch`, web SSE, CLI | Today tool-level progress reaches only an SSE route nothing renders (`web.py:600-640`) |
| **notify.py + job origin** | new / replaces three senders | `src/notify.py`; `jobs.origin` column `{channel, external_ref}` | Completion DMs reach ~3% of jobs because `_job_to_chat` is process memory (`telegram_bot.py:38,1028`) |
| **Per-provider quota** | rewrite of `quota.py` | `quota:{provider}:paused_until`, `quota:{provider}:window`, breaker keys | One global key today (`quota.py:21`); pause path has never fired in prod (state map §2.2) |
| **Vendor pollers** | new launchd/scheduler steps | Claude status-line probe, Codex `account/rateLimits/read`, Gemini day counter | `crosscut-subscription-automation-tos.md §3.10` |

### 1.2 Data model changes (migration 007, all nullable/additive)

`jobs`: `resolved_provider String(32)`, `task_class String(32)`, `lane String(16)` (owner|kernel|atlas), `priority SmallInt`, `origin JSONB` ({channel, external_ref, thread_ref}), `contract JSONB` (the resolved DoD), `dod_pass_count/dod_total SmallInt`, `grade_score Numeric(3,1)`, `grade_provider String(32)`, `merge_gate_verdict String(16)`, `terminal_reason String(32)`, `num_turns Int`, `duration_api_ms Int`, `input_tokens/output_tokens/cache_read_tokens/cache_write_tokens BigInt`, `cost_usd_list Numeric(8,4)`, `model_served String(64)`, `deliverables JSONB` (list of {kind, ref}). All of `num_turns/total_cost_usd/duration_api_ms/model_usage/stop_reason` are already on `ResultMessage` and dropped at `session.py:1095` (state map §2.1).

`verdicts`: `id, job_id, stage ∈ {evidence, grade, merge_gate, eval, dissent, retro}, grader_provider, grader_model, grader_job_id (nullable — when the grade ran as its own job), verdict ∈ {pass, fail, lgtm, changes_requested, blocker, concur, dissent, error, skipped}, score Numeric, findings JSONB [{id, severity, text, location, kind}], dod JSONB [{check, pass, detail}], cost_usd_list, latency_ms, created_at`.

`provider_ledger`: one row per model call, including the nested calls that are invisible today (router, learning, reviewer, judge — state map §2.2 "nested LLM calls invisible"): `ts, job_id, provider, model, task_class, purpose ∈ {main, subagent, router, learning, review, grade, judge, utility}, tokens_{in,out,cache_read,cache_write}, cost_usd_list, latency_ms, ttft_ms, terminal_reason, rate_limited bool, window_id`. Mirrors the common cross-lane schema in `crosscut-subscription-automation-tos.md §3.10a` and `crosscut-benchmarks-reviews.md §7 "Progress-visibility sink"` (Postgres as sink; no Langfuse/LiteLLM — 16 GiB / 4 GiB floors).

`job_events`: a projection of the JSONL audit (`{job_id, ts, kind, payload}`) for querying; JSONL stays the source of truth because reconcile, task lifecycle, review, learning and SSE replay read it (state map §6 row 1).

`provider_qualifications`: `provider, task_class, state ∈ {shadow, canary, qualified, demoted}, canary_share, since, evidence JSONB, changed_by (proposal id)`.

`schedules`: `task_class, provider_pref, priority, contract JSONB, misfire_policy`.

### 1.3 Executors / providers

| Executor | Auth | Capabilities (registry) | Containment | Used for |
|---|---|---|---|---|
| `claude_sdk` (today's path) | Max OAuth + `claude setup-token` in launchd env; never `--bare`; `ANTHROPIC_API_KEY` stays banned (`main.py:77-84`, INV-3) | agentic, tools, mcp, subagents, guard-hooks, structured-output | INV-17/INV-20 PreToolUse hooks (`guards.py:381-490`) + workspace clone; Seatbelt via `failIfUnavailable`/`strictAllowlist` for Telegram-originated jobs (`crosscut-subscription-automation-tos.md §3.8a`) | writer for every class; the only executor for `code-server`, `review-gate`, `_evaluate` (INV-21, plan §8); governors; trading analyst/validator |
| `codex_cli` | `codex login --device-auth` on the owner's ChatGPT plan; `~/.codex/auth.json` mode 0600 or `keyring`; `features.goals=false`; `otel.metrics_exporter="none"` (default is `statsig`, phones home: `chatgpt-openai.md §7`) | agentic, tools, structured-output (`--output-schema`), os-sandbox; **no MCP** (plan §5 caveat) | `--sandbox read-only` for grading, `--sandbox workspace-write` + network off for canary builds, scrubbed env, per-job clone (INV-21 a/b) | cross-vendor grader of Anthropic output; `code-project` canary on non-server repos |
| `http` (OpenAI-compatible completions) | `GEMINI_API_KEY` (unpaid, 250 RPD Flash), `OPENROUTER_API_KEY` (`:free` only), owner-added by hand (plan §8, C2) | structured-output (json schema / json_object + local validator) | no tools at all — containment by absence | utility classify/route/learning; grader on **public-content projections only** (unpaid Gemini trains on content: `gemini-google.md §3a`) |
| `local` (Ollama) | none | structured-output (`format` schema) | on-box; nothing leaves | mechanical checks (numbers/dates/link liveness pre-screen), routing first stage, learning classifier; `qwen3.5:4b` default, `9b` quality (`local-models-m4-16gb.md §7-8`); `OLLAMA_KEEP_ALIVE` short so no model is resident during job windows |
| `script` | none | none | subprocess | implements the dead `no_llm` flag (`skills.py:55`): evidence checks, schedule adherence, cost rollups |

### 1.4 Routing / policy

`routing-policy.yml` (data, lint-checked):

```yaml
task_classes:
  utility-classify: {writer: [local/qwen3.5:4b, gemini/gemini-3.8-flash, openrouter/:free, anthropic/claude-haiku-4-5], grader: none}
  chat:             {writer: [anthropic/claude-sonnet-5@low], grader: none}
  research-read:    {writer: [anthropic/*], grader: [codex/gpt-6-sol, gemini/gemini-3.8-flash#public, local/qwen3.5:9b#mechanical]}
  code-project:     {writer: [anthropic/*, codex/gpt-6-sol#ladder], grader: cross-vendor, gate: anthropic}
  code-server:      {writer: [anthropic/*], grader: [codex/gpt-6-sol#advisory], gate: anthropic}   # INV-21 pinned
  review-gate:      {writer: [anthropic/*]}                                                        # INV-21 pinned
  _evaluate:        {writer: [anthropic/*]}                                                        # INV-21 pinned
  trading-research: {writer: [anthropic/*], validator: anthropic, critic: [codex/gpt-6-sol#redacted, local/qwen3.5:9b#mechanical]}
pairing_rule: grader.provider != writer.provider   # enforced in code, not prompt
chain_terminates_in: included-cost                 # plan §10 decision 3
```

Capability matching keeps MCP/subagent skills on `claude_sdk` automatically (plan §6d). Frontmatter `model:` accepts `[provider/]model_id`; bare ids default to `anthropic/` (72 skills unchanged); `task_class:` is inferred from isolation+tags when absent (plan §6e).

### 1.5 Containment (INV-21 made real)

- Non-Anthropic executors run **only** at `isolation: workspace` in a per-job clone (`workspaces.py:127-170`), under the runtime's OS sandbox, with a scrubbed env (only their own auth), and with **no** MCP. Grader runs are read-only by absence of write tools (`codex exec --sandbox read-only`). Lint rule: `provider != anthropic ⇒ isolation == workspace` and `tags ∌ needs-*-mcp`.
- Guard adapters: the pure predicates in `guards.py` are load-bearing (254 fleet-wide denials); the hook transport is SDK-only. `ExecSpec.guard_profile` is honoured by (a) SDK hooks, (b) OS sandbox read-only mounts of `protected_roots()`, or the executor is refused. Two protected-path edits batched into one owner PR: add `GEMINI_API_KEY|OPENROUTER_API_KEY|CODEX_API_KEY|OPENAI_API_KEY|XAI_API_KEY` to the deny regex at `guards.py:148-149,261-262` (today only the Anthropic literal is guarded: state map §7 item 5), and a broker-host deny (`api.tradier.com|sandbox.tradier.com|/v2/orders`) closing the INV-22 server-side gap (`SYSTEM.md:130`).
- Untrusted input (Telegram text, fetched pages, MCP free-text) reaches only A-rated lanes: Claude `-p` with sandbox forced, Codex `exec` (`crosscut-subscription-automation-tos.md §3.8a`, `crosscut-benchmarks-reviews.md §7` injection table). Gemini/OpenRouter/local get owner-authored prompts and pre-fetched public inputs only.

### 1.6 Event / audit model

New audit kinds (additive; existing 33 unchanged): `contract_resolved{checks,grader}`, `evidence_check{check,pass,detail}`, `evidence_manifest{artifacts}`, `grade_requested{provider,model}`, `grade_done{provider,verdict,score,findings_n,cost}`, `merge_gate_verdict{verdict}`, `provider_selected{provider,reason∈policy|pin|fallback|ladder}`, `provider_fallback{from,to,cause}`, `quota_window{provider,window,used_pct,resets_at}`, `deliverable_published{kind,ref}`, `progress{stage,pct,last}`. All are also published on `jobs:stream:<id>` (today only text + tool_use are: `session.py:1146-1157`) and mirrored into `job_events`. Terminal detection moves from the banner regex (`session.py:495-534`) to executor-reported `terminal_reason` using the SDK's typed `api_error_status`/`stop_reason`; the unrecognised-model silent-success hole (`claude-anthropic.md §7` gotcha: empty result, `duration_api_ms: 0`, no `is_error`) is closed by asserting `model_usage` contains the requested model.

## 2) Interfaces & visibility

### 2.1 Telegram (phone) — commands and cards

Registered commands (fixes the four ghost commands: `/rate`, `/status <prefix>`, `/cancel <prefix>`, `/proposals` — state map §5 item 13):

| Command | Behaviour |
|---|---|
| `/task [--class=] [--provider=] [--done=check,…] <text>` | as today (`telegram_bot.py:150-180`) plus contract overrides; unknown provider/model rejected at enqueue (fail-closed), not at session time |
| `/watch <job8>` | pins a **live progress card** edited in place (≤1 edit/10 s, Telegram-safe) until terminal |
| `/done <job8>` | the **deliverable card** (below) |
| `/queue` | queued/deferred/blocked jobs with *why* (lane full, provider paused, depends_on, awaiting approval) and age |
| `/providers` | quota/health/breaker/spend per lane; buttons `pause <id>` / `resume <id>` (plan §6f) |
| `/schedules` | next 10 runs + adherence flags; buttons `run now`, `pause`, `skip next` |
| `/scoreboard [class]` | top-line provider scoreboard for a task class |
| `/cancel <job8>` | durable cancel: running (interrupt) **and** queued (LREM + status flip; today queued ids are a no-op: `main.py:1368-1404`) |
| `/rate <job8> 1-5` | real command; kept because it is advertised, but no rollup depends on it any more |
| `/clear` | requires `/clear confirm` |

**Progress card** (`/watch`, also auto-sent for owner-launched jobs):

```
🔄 a1b2c3d4 · atlas-value-theses · anthropic/claude-opus-5 · 04:12
stage: executing · turn 18/50 · last: Bash(pytest -q) ✓ 0.8s
DoD 2/5  ✅ card_preregistered  ✅ trials_line  ⬜ walkforward_folds  ⬜ memo_sections  ⬜ pushed
tokens 312k (cache 91%) · est $0.11 list · lane atlas · quota 5h 42% ↻15:10 · wk 61%
[Cancel] [Details] [Mute]
```

**Deliverable card** (`/done`, and the completion DM for every job with an origin, scheduled ones included — today all failed-notify paths require `task_id`: state map §5 item 7):

```
✅ a1b2c3d4 DONE · research-report · 6m40s · $0.09 list · anthropic/claude-sonnet-5
DoD 5/5 ✅ · grade 8/10 (codex/gpt-6-sol, 2 findings) · anchor LGTM
evidence: projects/research/nvda-2026-09-24.md · commit 3f2a1c · https://…/reports/nvda
findings: (1) §3 cites a Q2 figure without a filing URL · (2) confidence stated without base rate
[Open] [Reopen] [Dissent→fix round] [Rate]
```

Failure/ungraded variants: `⚠️ DONE-UNVERIFIED (DoD 3/5: pushed ✗, url_200 ✗)`, `❌ FAILED (terminal_reason=rate_limited, requeued front, resumes 15:10)`, `🟡 GRADE SKIPPED (codex paused; anchor-only)`.

**Providers card** (`/providers`, also DM'd on state change):

```
providers · 14:05
anthropic  ● healthy   5h 42% ↻15:10 · wk 61% ↻Mon 09:00 · running 2/2 · today 31 jobs · $4.10 list
codex      ● healthy   5h 8% · wk 12% (rateLimits RPC) · running 0/1 · today 9 grades · plan Free
gemini     ● healthy   day 57/250 · running 0/1 · today 57 utility · public-only
local      ● idle      qwen3.5:4b unloaded · today 112 classify · 0 errors
openrouter ○ degraded  2 :free links delisted 09-22 → chain terminates at haiku
breakers: none · paused: none · last quota event: anthropic rate_limit 09-23 22:14 (resumed 23:00)
```

### 2.2 Web (laptop)

Replace the inline htmx string (`web.py:646-847`) with a small static app (`static/app/`) behind Cloudflare Access (hosting change; today a single shared token weaker than the projects it manages — state map §2.3). Views: **Jobs** (live via SSE, filters by lane/provider/class/status), **Job** (progress record, DoD checklist, evidence links, verdicts with findings, transcript replay from JSONL, cancel/reopen/approve/reply), **Deliverables** (feed of `deliverable_published` with links), **Providers** (quota gauges, spend-list-equivalent per day, breaker history, per-provider p50/p90 latency), **Schedules** (next runs, adherence DARK/NEVER_RAN/STUCK from `schedule_adherence.py`, run-now/pause), **Scoreboard** (per task class), **Queue** (blocked-why). Web launches create a Task and an origin so they get lifecycle cards (today `POST /api/jobs` never creates a Task: `web.py:399-405`). REST: `GET /api/jobs/{id}/contract|verdicts|evidence`, `GET /api/providers`, `GET /api/scoreboard?task_class=`, `GET /api/queue`, `POST /api/schedules/{id}/run`.

### 2.3 CLI (laptop terminal)

`python -m src.cli` (thin wrapper `bin/ai`): `ai task …`, `ai watch <id>` (streams the progress record), `ai done <id>`, `ai providers`, `ai queue`, `ai scoreboard`, `ai schedules`, `ai retro`. Stamps `created_by='owner-cli'` and an origin `{channel: cli}` so the ad-hoc `owner-terminal/owner-dispatch/owner-rescue` strings disappear (state map §2.3).

### 2.4 Vendor apps

Not the surface of record. Codex `/status` and chatgpt.com/codex/settings/usage are the owner's human check on the ChatGPT window; Claude `/usage` is the human check on the Max window. Claude cloud Routines are **optional cold standby** for repo-scoped jobs when the Mini is down (first-party, draws subscription, daily run cap, 1 h minimum: `crosscut-subscription-automation-tos.md §3.1`) — owner decision 8, default off.

### 2.5 Cost / quota / schedule visibility

- **Quota**: Codex is the only subscription lane with a native remaining-budget read (`account/rateLimits/read` + `updated` push: `chatgpt-openai.md §7`); Claude exposes `rate_limits.five_hour/seven_day.{used_percentage,resets_at}` only to a status-line command in an interactive session, so a scheduled 1-token probe session dumps it to a file (`claude-anthropic.md §3` "Progress visibility"); Gemini is a day counter vs 250; local has none. Everything is written as `quota_window` events and shown as gauges; where inferred, the row is labelled `inferred`.
- **Cost**: `cost_usd_list` is list-price-equivalent computed from tokens (subscription marginal cost is $0; the label says so). Daily rollup per provider/lane/skill; monthly DM. Calibration anchor: the measured job shape (~98.5k in at 82% cache, ~1.9k out) prices Sonnet-class at ~$0.08 list-equivalent, i.e. ~$8–14/month for the whole scheduled load (`crosscut-finance-trading-ai.md §3` "Empirical calibration").
- **Schedule adherence**: adherence findings surface on `/schedules` and the web view immediately, not only via the 07:15 launchd DM; scheduled failures DM at once with `terminal_reason`.

## 3) Effectiveness

### 3.1 Definition of done (Deliverable Contract)

Declared in frontmatter (`done:` block), overridable/extendable per job via payload `contract`, resolved once at session start and audited as `contract_resolved`. Checks are **deterministic and run by the runner** (`ScriptExecutor`), never by the model:

| Check kind | Args | Typical class |
|---|---|---|
| `file_exists`, `sections_present`, `citations_min`, `word_range` | path, sections[], min | research-read, trading memos |
| `tests_green` | cmd (path-conditional pytest, `npm test`) | code-project, code-server |
| `git_pushed`, `changelog_touched`, `lint_green` | — (workspace tier: commits reached canonical via `workspaces.py:247-270`) | code-* |
| `url_200`, `healthcheck_green` | url | project delivery |
| `db_row` | read-only SQL against the atlas DB (`trials.jsonl` line, `swing.runs` status, `value.theses` count) | trading-research |
| `no_marker` / `marker_present` | `TASK_QUESTION:` absent, `TASK_COMPLETE:` present | all |
| `schema_valid` | JSON schema over the structured final output | utility, grading |
| `budget_within` | tokens/turns/time ceilings | all |

Default contract for generic `task` jobs and every skill without a `done:` block: `marker_present(TASK_COMPLETE) ∧ no_marker(TASK_QUESTION) ∧ claimed_files_exist ∧ budget_within`. Outcome states: `completed` (all checks pass), `completed_unverified` (a check failed, `on_fail: flag`), `failed` (`on_fail: fail`), `fix_round` (`on_fail: fix-round`, max 2, reusing the existing evaluator fix loop at `main.py:949-985`). Default `on_fail` is `flag` fleet-wide; `fail` for deploy and trading-ledger skills. Owner decision 10 confirms the default.

### 3.2 Evidence

The runner writes `<job>.evidence.json` from (a) the check results, (b) artifacts the model declares in a final-text block `<<<EVIDENCE … EVIDENCE>>>` (same mechanism as `<<<TASK_PLAN>>>`, `session.py:405-460`) validated to exist, (c) the workspace diff summary, (d) `deliverable_published` refs. `Job.deliverables` is the queryable list; cards link to it. Evidence is what graders receive — never the raw transcript alone — so grading is about the deliverable, not the process.

### 3.3 Review / grading — vendor ≠ writer

Three belts, each recorded as a `verdicts` row:

1. **Evidence checks** (no LLM, above).
2. **Grader** (`grading.py`): picks `grader.provider != writer.provider` from the class policy; runs read-only with the evidence bundle, the class rubric (reusing `evals/cases/<skill>.yml` rubrics), and a structured-output schema `{verdict, score 0-10, findings[{severity,text,location,kind}], dod_items[]}`. Codex: `codex exec --json --ephemeral --sandbox read-only -m gpt-6-sol --output-schema grade.json` (`chatgpt-openai.md §7`). Gemini unpaid / local: only on the **public-content projection** of the bundle (§6.3). Fail-closed on error (`verdict=error` → card shows "ungraded"), bounded to 600 s like `_maybe_review`. Anthropic-written work is graded by Codex first (highest independence: `crosscut-subscription-automation-tos.md §5.2a`), Gemini second; Codex-written canaries are graded by Anthropic (Sonnet 5). Kimi/MiniMax/DeepSeek are never graders of Claude output (named in the distillation disclosures, same source).
3. **Trust gate** (unchanged in authority, changed in recording): the in-session `code-review` subagent remains the only INV-13 LGTM. Its verdict is captured structurally — the subagent's `output_format` schema is the same grade schema, and the parent records it as `merge_gate_verdict` — and `_maybe_review` (`review.py:247-256`) runs **pre-push on the workspace diff before `sync_canonical`** (`session.py:1038-1043`) with the 600 s timeout counted as `changes_requested`, closing the documented "skipped without verdict" gap (`main.py:620-626`). A cross-vendor grader on `code-server` output is advisory: it can add `dissent` and lower the scoreboard, never block or approve (INV-21 c; owner decision 1 relaxes plan §7's "GPT reviewing anything is out of scope" only to this advisory extent).

Independence is measured, not assumed: monthly pairwise Jaccard of normalised findings between grader lanes and the anchor; a pair above ~0.7 is not a second opinion and is rotated out (`runtimes-aggregators.md §3(g)`).

### 3.4 Provider scoreboard

`scoreboard` view keyed by `(provider, model, task_class)` over `verdicts ⋈ provider_ledger ⋈ jobs`: `n`, `dod_pass_rate`, `grade_mean`, `grade_p10`, `dissent_rate` (grader disagreed with anchor), `unverified_rate`, `escalation_rate`, `fail_rate` by `terminal_reason`, `cost_usd_list_p50`, `latency_p50/p90`, `ttft_p50`, `quota_share_pct`, `independence_jaccard`, `ladder_state`. Served at `/api/scoreboard`, `/scoreboard`, and the web view; consumed by the policy engine and the retro job. It replaces the never-called `skill_performance/writeback_frequency/escalation_frequency` (`retrospective.py:39,99,120`) and gives review-and-improve real per-skill×provider data instead of `GROUP BY kind`.

### 3.5 Qualification ladder

Per `(provider, task_class)`: **shadow** (provider runs `evals/cases` offline and/or grades in parallel with no routing effect; `evals/run.py --provider` persists results to `verdicts(stage=eval)`) → **canary** (≤10% of low-stakes live jobs, always anchor-graded, escalation retries on the qualified provider) → **qualified** (enters the writer chain) → **demoted** (breaker trips on `dod_pass_rate` or `grade_mean` delta vs anchor over a rolling 20 jobs). Transitions are `proposals` rows of the never-used `default-model` kind (state map §2.5: 0 filed), owner-approved while a lane is young, auto for demotion (plan §6g). Eval coverage target: a case file for every routable skill (7/72 today).

### 3.6 Retrospectives comparing vendors

`retro` skill (Anthropic, read-only, weekly Sunday, replaces the idle-triggered `review-and-improve` at opus-4-7/max — 28 runs/30 d, ~1.3 M cache-read tokens each, for 11 pending proposals: state map §2.5) reads the scoreboard and writes `docs/retro/<week>.md`: per task class, which vendor delivered (DoD, grade), where they disagreed, cost and latency, quota incidents, ladder moves proposed, plus a **monthly cost report** DM. Deterministic pre-pass in `script` executor produces the tables; the LLM writes the narrative only.

## 4) Scheduling across vendors

- **One scheduler of record** (`main.py:1327-1362`), not vendor-native schedulers (ChatGPT scheduled tasks, Grok Build tasks, Gemini Scheduled Actions are consumer-UI features with no run records the server can grade). Fixes folded in: commit-before-RPUSH, slot-based `next_run_at`, `misfire_policy ∈ {skip, catch_up_one}` per row, `kind` validated at enqueue.
- **Schedules as data**: `schedules.yml` (tracked) with a Python seeder that validates cron collisions and DST pairs, replacing the 41× `pipenv run python | psql` shell loop (`scripts/seed-schedules.sh:22-47`); rows carry `task_class`, `provider_pref`, `priority`, `contract`, `session_timeout_seconds`. `/schedule add` on the phone becomes a form (kind, cadence preset, project) that writes the same row.
- **Lanes and priority**: `jobs.lane` derived from `created_by` (owner > kernel > atlas); a sorted-set queue with one reserved owner slot so `/task` never queues behind daily atlas rows (state map §2.2 "FIFO with no priority"); per-lane caps (atlas ≤ 1 of 2 prod slots by default; MISSION §K "kernel ops win").
- **Per-provider windows, not slots**: subscription lanes are token-window-limited, not slot-limited (`runtimes-aggregators.md §3(a)`, `crosscut-benchmarks-reviews.md §7 Concurrency`). Fan-out starts at Claude 2 (prod `MAX_CONCURRENT_JOBS=2`), Codex 1 (one `auth.json` per serialized stream — concurrent refreshes rotate tokens against each other), Gemini 1, local 1; raised only on a week of clean `rate_limited=false` telemetry. A memory guard (free RAM < 3 GB ⇒ no new SDK subprocess; ~148 MB RSS each today, 1 GiB/agent floor per Anthropic's hosting guide) sits above the semaphore.
- **Class-aware pause**: `QuotaExhausted{provider}` pauses only that provider's key; a job waits only when no provider in its class chain is healthy (plan §6f). Anthropic pause still front-requeues (INV-12) and pauses the pinned classes exactly as today. Utility calls pre-emptively reroute to local/Gemini when Anthropic's 5-h window passes 80%.
- **Pre-dispatch gating**: before dispatch, the scheduler reads the latest `quota_window` per provider and refuses to launch a job whose p90 token estimate (from the ledger for that skill) exceeds the inferred remainder; Codex's RPC number calibrates the inference for the others.
- **Credential canaries**: daily `claude -p 'ping'` and `codex exec --ephemeral "ok"` (Codex refreshes only during use and an idle lane lapses: `crosscut-benchmarks-reviews.md §7 Credential lifecycle`); T−30 d alarm on the `setup-token` mint date; an auth failure parks the lane before the first job of the day.

## 5) Project delivery path

Pipeline for a project deliverable (`projects/<slug>` with the delivery contract in `delivery.py:130-147`):

1. **Contract**: manifest gains `deliverables:` (what shipped means: build green, healthcheck 200, URL 200, tests, CHANGELOG) → becomes the job's DoD.
2. **Plan** (Anthropic, `plan` → DAG via `plans.py`) with each subtask carrying its own checks.
3. **Build**: Anthropic by default; Codex `code-project` canary on non-server repos once `qualified` (workspace clone, Seatbelt `workspace-write`, network off, no MCP).
4. **Evidence checks** (deterministic) in the workspace before anything leaves it.
5. **Grader** (cross-vendor) on the evidence bundle → `verdicts`.
6. **Trust gate**: Anthropic `code-review` verdict recorded pre-push; `changes_requested` parks the workspace (clone kept, as failures are today) and opens a fix round instead of pushing.
7. **Push → gated deploy** (`server-deploy`/`atlas-redeploy`, unchanged executor skills; `deploy-director: verify` re-checks post-conditions) → `deliverable_published{url, commit, healthcheck}`.
8. **Deliverable card** to the origin channel with links; web Deliverables feed.

Server-code lane (`code-server`): writer and gate Anthropic-only; cross-vendor grade advisory. INV-4 protected paths keep requiring explicit owner approval. Atlas two-repo copies get a lint that diffs `atlas/integrations/ai-server/skills/` against `skills/` (15/26 drifted today, state map §2.6).

## 6) Trading research automation within INV-22

**What "automate trading" means here**: research, theses, adversarial review, evaluation, paper/shadow loops, sentiment as a feature — never an order path. The only order path stays `atlas/swing/swing/executor.py --submit` behind `risk.validate` (INV-22, C11); nothing in this design adds a broker call, a broker MCP, or a live key on the server.

### 6.1 What runs where

| Stage (existing atlas loop) | Executor | Change |
|---|---|---|
| Research cycle, thesis composition, quant sweeps | Anthropic (Max, "Help improve Claude" **off** → 30-day retention, no training: `claude-anthropic.md §3` data table) + Alpaca-paper/EDGAR/Massive/Finnhub MCP | DoD checks from the constitution: card pre-registered, `trials.jsonl` line before verdict, walk-forward folds present, DSR computed, memo sections, no web tools in evaluation runs |
| Adversarial validator | Anthropic clean-context subagent (unchanged; separated duties C22) | verdict recorded as `verdicts(stage=grade, provider=anthropic)` |
| **Cross-vendor critic** (new) | Codex `gpt-6-sol` read-only on the **redacted projection**; local `qwen3.5:9b` for mechanical checks (numbers vs tool outputs, dates vs cutoff/look-ahead, link liveness) | writes `DISSENT/CONCUR` ledger entry + `verdicts(stage=dissent)`; additive after the Anthropic validator, never replaces it |
| Governors (grade from DB rows only) | Anthropic, read-only | verdicts recorded; governor inputs include critic dissent rate |
| Paper supervision / swing decisions (inside the kernel's bounded candidates) | Anthropic sonnet | unchanged; `db_row` checks make "completed ≠ productive" visible (37/37 `provisioning_gap` runs today report success) |
| Sentiment feature (optional) | xAI API `x_search` with allowed handles + date window → append-only snapshot table, overlay tag only, forward-paper only (`grok-xai.md §6`, `crosscut-finance-trading-ai.md §7`) | **metered; owner decision 5**, default off |
| Transcripts/estimates beyond EDGAR (optional) | Perplexity Agent API `finance_search` | **metered; owner decision 5**, default off |

### 6.2 Which vendor adds what

Anthropic: analyst, validator, governor (trust anchor; Vals Excel/Tax top-3, `00-comparison-matrix.md §3` trading row). Codex/GPT-6: independent reasoning dissent on thesis logic and look-ahead (`chatgpt-openai.md §8` "it should review, not decide"). Local Qwen: zero-egress mechanical verification. Gemini unpaid: never for theses (trains on content); usable only to critique fully public memos (e.g. quant reports with no positions). Grok: X sentiment feature only, if approved. Population-scale 2026 evidence says no vendor has directional edge (`crosscut-finance-trading-ai.md §1, §8`), so no vendor is ever a decision-maker.

### 6.3 Data / credential boundaries

- **Redacted projection**: before any non-Anthropic critic sees a memo, a deterministic redactor strips positions, sizes, ledger rows, account values and owner identifiers; the projection is what leaves the Anthropic lane. Anthropic keeps full context (30-day retention, training off). This satisfies the data-handling matrix (`crosscut-benchmarks-reviews.md §7` "Data-handling"): Codex on plan auth is "unknown → use API key for theses", which owner policy excludes, so theses themselves never go there.
- **Credential scoping**: `env_files` today copies the whole atlas `.env` into every atlas workspace (state map §2.6); scope becomes per skill (`env_files: [.env.trader]` etc.), Tradier sandbox token only in swing workspaces, vendor keys never in any atlas workspace, and non-Anthropic executors never receive atlas env at all.
- **Server-side INV-22 deny**: broker-host pattern in `guards.py` (protected; owner PR) plus a Tradier remote-MCP ban in lint (ships live order tools in the same server: `crosscut-finance-trading-ai.md §3`).
- **AUP posture**: outputs are owner-only research memos, never advice to a second person, human on the order path — inside every vendor's advice/reliance clause (`crosscut-finance-trading-ai.md §6`).

## 7) Vendor plan

| Vendor / lane | Surface | Auth | Cost path | ToS status (research) | Task classes here |
|---|---|---|---|---|---|
| **Anthropic Claude Max** | Agent SDK (pinned `<0.2`) + bundled CLI; never `--bare`; OTEL to local collector | own Max account; `/login` Keychain + `claude setup-token` in launchd env (1-year); training toggle off | subscription (already paid); $0 marginal | **Yes\*** — unmodified binary, own plan, "ordinary, individual usage"; policy volatile, `--bare` may become `-p` default (`crosscut-subscription-automation-tos.md §3.1, §3.7`) | writer all classes; anchor gate; `code-server`, `review-gate`, `_evaluate` pinned; trading analyst/validator/governor; chat (Sonnet 5 low) |
| **OpenAI Codex CLI** | `codex exec --json --output-schema`, `--sandbox read-only|workspace-write`; app-server `account/rateLimits/read` for quota | `codex login --device-auth`, owner's ChatGPT plan; `features.goals=false`; `otel.metrics_exporter=none`; model pinned (`-m gpt-6-sol`; rate-limit prompt silently retargets Luna) | **Free** (owner decision 2026-08-17: probing); likely Plus $20 for grader volume — owner decision 2 | **Gray/Yes\*** — owner-only jobs on plan auth tolerated, API key "recommended" for CI; goal mode burns the window (`chatgpt-openai.md §7-8`, `crosscut-tos §3.2`) | grader of Anthropic output (research, code-project advisory on code-server); trading critic on redacted projections; `code-project` canary → qualified |
| **Google Gemini** | `gemini -p --output-format json` or HTTP `generateContent` on `gemini-3.8-flash` | unpaid AI Studio key (250 RPD, Flash only), owner-added | $0 | **Yes** for API key; unpaid tier **trains on content, human review** (`gemini-google.md §3a`); Antigravity/Gemini OAuth via third-party tools **banned** — not used | utility classify/learning; grader on **public-content** bundles only; never theses |
| **Local Ollama** | `/api/chat` with `format` schema; `qwen3.5:4b` / `9b`, `embeddinggemma`; stale 14 GB of weights removed | none | $0 | n/a (MIT runtime; Apache-2.0 weights) (`local-models-m4-16gb.md §7-8`) | routing first stage, learning classifier, mechanical checks, embeddings; never coding/research/adversarial review |
| **OpenRouter `:free`** | OpenAI-compatible HTTP, `provider.zdr` where offered | key, owner-added | $0 (**no metered spend** — declined 2026-08-17) | Allowed (API); high churn, 20 RPM / 50–1,000 req/day (`runtimes-aggregators.md`) | utility middle link only; never load-bearing |
| **xAI API** (optional) | `/v1/responses` + `x_search` | key | metered ~$0.30/job incl. posts | Yes (API); AUP securities clause → research label only (`grok-xai.md §6, §8`) | sentiment feature column — **owner decision 5**, default off |
| **Perplexity Agent API** (optional) | `finance_search` | key | metered $5/1k + tokens | Yes (API); consumer plan banned | transcripts/estimates — **owner decision 5**, default off |
| **Claude Routines** (optional) | `/schedule`, `/fire` API | subscription login | draws subscription; daily run cap | Yes (first-party) | cold standby for repo-scoped jobs when the Mini is down — **owner decision 8** |

Excluded on purpose: Antigravity/Gemini OAuth from the orchestrator (written breach + bans), Alibaba/Xiaomi token plans (written non-interactive prohibition), Perplexity consumer, DeepSeek (no subscription; PRC storage), Kimi/MiniMax as graders (distillation exposure), LiteLLM/Langfuse daemons (memory), Cursor/Copilot/Kiro seats (cost without a task class they win), any second consumer seat per vendor (multi-account = the one confirmed permanent-ban pattern).

## 8) Migration & rollout

Everything is additive and flag-guarded; the current Anthropic-only behaviour is the kill-switch state (`ROUTER_PROVIDERS_ENABLED=anthropic`, plan §2) plus `GRADING_ENABLED=off`, `CONTRACTS_MODE=observe|enforce`, `LANES_ENABLED=off`.

| Phase | Scope | Entry | Exit | Keeps running / kill switch |
|---|---|---|---|---|
| **P0 Foundations** (wk 1–2) | `providers.yml` (anthropic-only entries) + registry consumed by aliases/VALID_MODELS/dropdown; executor extraction behind `Executor` protocol; migration 007; capture the dropped `ResultMessage` fields; record `merge_gate_verdict`; contracts framework with deterministic checks in **observe** mode (events only, status unchanged); `notify.py` + `jobs.origin`; ghost commands fixed; `/clear confirm` | owner signs off design; MISSION already amended | pytest + lint green; replayed job → identical audit sequence (plan §7 R2 gate); 100% of new jobs have `contract_resolved` + evidence events; `resolved_provider='anthropic'` on every job | all 41 schedules unchanged; `ROUTER_PROVIDERS_ENABLED=anthropic` |
| **P1 Visibility** (wk 2–4) | progress record + `/watch` + `/done` + `/queue` + `/providers`; scheduled-failure DMs; web app v1 (Jobs/Job/Providers/Schedules) behind CF Access; Claude status-line probe + Codex rateLimits poller (Codex read-only install); cost columns + daily rollup; CLI | P0 exit; CF Access decision (owner decision 7) | every job with an origin gets a completion card (measured ≥95% vs ~3%); quota gauges populated for anthropic; owner uses `/watch` for a week without asking for SQL | old dashboard route kept until v1 signed off |
| **P2 Cross-vendor grading, shadow** (wk 4–7) | Codex device-code login + `codex_cli` executor (read-only); Gemini unpaid key + `http` executor; Ollama qwen3.5:4b/9b; `grading.py` in **shadow** (verdicts recorded, cards show them, no status effect); redacted projection; evals → DB with `--provider`; independence measurement; scoreboard v1; `retro` skill | owner adds keys (auth config) and completes the two logins; owner decision 1 (advisory graders) and 2 (ChatGPT tier) | ≥200 graded jobs; grader error rate <5%; Jaccard(anchor, codex) reported; first retro delivered with real numbers | `GRADING_ENABLED=off` reverts to today |
| **P3 Routing by evidence** (wk 7–10) | per-provider quota keys + breakers; class-aware pause; priority lanes + owner slot; memory guard; utility lane to local→gemini→openrouter→haiku (plan R1); contracts → **enforce** (`completed_unverified` appears); ladder live: Codex `code-project` canary on a non-critical project; review-and-improve replaced by retro + scoreboard SQL | P2 exit; routing-precision eval ≥ Haiku baseline on router cases | simulated Anthropic pause drill: routable lanes keep draining, pinned lanes pause, DM fires (plan R4 gate); canary DoD/grade within baseline; monthly cost report delivered | `LANES_ENABLED=off`, `ROUTER_PROVIDERS_ENABLED=anthropic`, `CONTRACTS_MODE=observe` |
| **P4 Trading critic + hardening** (wk 10–13) | critic stage in atlas research loops (LOOP.md §7 front door: evidence-gated owner decision); constitution DoD checks; per-vertical `env_files` scoping; two-repo drift lint; **owner PRs**: guards.py vendor-key + broker-host denies, `isolation` default flip per vertical + allowlist shrink, unwired lint checks; schedules-as-data seeder | P3 exit; atlas governor consumes verdicts; owner decision 3 (protected batch) | critic dissent rate reported per vertical; zero non-Anthropic executor ever launched with atlas env (audit assertion); INV-22 deny test green | critic flag per vertical; seeder keeps `seed-schedules.sh` semantics |

Ops debt fixed alongside (cheaper than most of the above, state map §6 last row): rclone R2 backup + `pg_dump atlas` + sealed `.env`/cloudflared copies, `autorestart 1`, remove stale Ollama weights.

## 9) Deleted / rewritten vs kept

**Kept (load-bearing)**: JSONL audit + summary files and their kinds; text-marker lifecycle contract; workspace clone + ff-sync (INV-16); guard predicates (`guards.py` pure functions, 56 tests); fail-closed skill resolution, tighten-only isolation, deploy-authority gate; SKILL.md frontmatter as the runtime contract (extended backward-compatibly); `enqueue_job` + `jobs:queue` + Job-row-as-truth + slot-before-BLPOP (priority added on top, shape unchanged); out-of-band launchd alerters and the edge Worker; in-session `code-review` as the merge gate; atlas kernel order path + tripwires; SDK `<0.2` + `mcp<2` pins (isolated behind the executor seam, not removed); the escalation ladder (generalised to `{provider,model,effort}` with error-class gating so quota/auth/network classes no longer spawn `self-diagnose` — 21% of all jobs today).

**Rewritten (accidental complexity)**: `_build_options` monolith → `ExecSpec` + adapters; `_run_in_process` → `ClaudeSdkExecutor`; the four copy-pasted `query()` loops (`llm_router.py:156-168`, `learning.py:266-278`, `review.py:258-278`, `evals/run.py:74-100`) → one `utility_call(provider, model, system, user, schema)` seam; `_MODEL_ALIASES`-as-allowlist → registry; global `quota:paused_until` → per-provider; banner-regex terminal detection → `terminal_reason`; `_job_to_chat` dict → persisted origin; three Telegram senders + `_error_safe` self-diagnose dispatch → `notify.py` with a capped auto-dispatch; inline-HTML dashboard → static app; `seed-schedules.sh` → validating seeder; `healthcheck-all.sh` raw-SQL enqueue → `enqueue_job`; review-and-improve at opus-4-7/max → deterministic scoreboard + weekly retro.

**Deleted**: `JobKind` enum and the `notify` ghost; dead `on_quality_gate_miss`/`post_review.reviewer_model` surface (or implemented via the registry); rating buttons on every card (rating stays as an optional command); 14 GB of stale Ollama weights; the `_MODEL_BUDGETS` table (context windows come from the registry). Nothing under `skills/` or `projects/` is deleted (hard rule).

## 10) Risks & mitigations

| Risk | Mitigation |
|---|---|
| Anthropic re-gates `-p`/SDK on subscriptions or `--bare` becomes the `-p` default (auth break) (`claude-anthropic.md §3, §7`) | pin CLI/SDK; smoke-test `claude -p ping` on every bump; `setup-token` + Keychain both present; Routines as cold standby (decision 8); design already portable to usage credits |
| Codex plan-auth Gray status; ChatGPT Free may not carry grader volume; goal mode burns window | owner-only outputs; `features.goals=false`; `-m` pinned; rateLimits pre-dispatch gate; if Free cannot sustain ~60–120 grades/month, Plus $20 (decision 2) or fall back to Gemini-public + local for the shadow phase |
| Free-tier churn (OpenRouter delistings, Gemini quota rugs) — accepted by the owner 2026-08-17 | every chain terminates in an included-cost provider; breakers log loudly; `/providers` shows degraded links |
| Correlated reviewers (harness and distillation effects) | measured Jaccard per pair; Kimi/MiniMax/DeepSeek excluded as graders of Claude; rotate pairs above 0.7 |
| Grader gaming: writer optimises for the rubric | deterministic checks carry the DoD; graders see evidence bundles, not the writer's self-report; anchor gate unchanged |
| Weak DoD makes `completed` look better than it is | `completed_unverified` is a visible state; scoreboard reports `unverified_rate`; retro flags skills whose contracts are default-only |
| Extra Claude quota if graders fall back to Anthropic | fallback for grading is `skipped`, never Anthropic (asymmetry preserved); utility calls leave the Max window first |
| Memory on the 16 GB Mini (SDK subprocess ~148 MB, local model 3–7 GB, Codex/Node CLIs 0.2–0.5 GB) | memory guard above the semaphore; `OLLAMA_KEEP_ALIVE` short; no LiteLLM/Langfuse; measure RSS before any new daemon |
| Hot-path refactor regressions (P0) | behaviour-identical extraction with the replay gate; kill switches; `_build_options`/executor gain the tests they lack (zero today) |
| Data leakage of theses to a training lane | redacted projection is deterministic and tested; non-Anthropic executors never receive atlas env; lint forbids non-Anthropic on skills tagged `trading-sensitive` |
| Owner bandwidth (two logins, keys, ~6 protected-path approvals) | batched into three owner PRs and one key-provisioning session; each phase ships value without the next |

## 11) Owner decisions required

1. **Advisory cross-vendor graders on Anthropic output** — relaxes plan §7 "GPT reviewing anything is not in-plan" to *advisory only* (dissent + scoreboard; LGTM stays Anthropic, INV-21 unchanged). Recommended: yes.
2. **ChatGPT tier for Codex** — stay Free (probing) or Plus $20/month once grading leaves shadow. Recommended: Free through P2, decide on measured grade volume.
3. **Protected-path batch** (one PR, INV-4): `guards.py` vendor-key deny names + broker-host deny (INV-22 server-side); `lint_docs.py` allowlist shrink + `isolation` default flip per vertical + wiring the four unwired checks; executor-skill edits for pre-push review recording. Recommended: approve after P2.
4. **Gemini unpaid key scope** — confirm public-content-only use (utility + public memo critique), never theses or Telegram text. Recommended: yes.
5. **Optional metered side-cars** — xAI `x_search` sentiment feature (~$1–5/month) and Perplexity `finance_search`; both violate "free tiers only" unless explicitly approved. Recommended: defer; revisit after critic data.
6. **Account hygiene by hand (auth config)** — verify "Help improve Claude" is **off** on the Max account; mint `claude setup-token`; complete `codex login --device-auth`; add `GEMINI_API_KEY`/`OPENROUTER_API_KEY` to `.env`. Sessions never do this.
7. **Cloudflare Access in front of the dashboard** (hosting config change).
8. **Claude Routines as cold standby** for repo-scoped jobs when the Mini is down (draws subscription; daily cap). Recommended: defer.
9. **Contract enforcement default** — `on_fail: flag` fleet-wide with `fail` for deploy/trading-ledger skills, or stricter. Recommended as stated.
10. **Atlas LOOP.md §7 front door** — critic stage and per-vertical env scoping are model/cadence changes in the atlas loops; confirm they may land as evidence-gated proposals.

## 12) Effort and cost

**Effort**: ~13 agent-weeks across P0–P4 (P0 2, P1 2, P2 3, P3 3, P4 3), each phase independently shippable; plus ops-debt fixes (~0.5 week). Owner time ≈ 15–25 hours total: one key/login provisioning session (~1 h), three protected-path PR reviews (~1 h each), phase sign-offs (~1 h each), and ~1 h/week reading `/done` cards and retros during rollout.

**Monthly cost** (incremental over today's Max seat): Claude Max unchanged ($100 or $200 — tier not recorded in-repo); Codex $0 (Free) or $20 (Plus); Gemini $0; local $0; OpenRouter $0; optional xAI/Perplexity side-cars $1–10 only if decision 5 approves. **Total incremental: $0–20/month, $0–30 with side-cars.** List-equivalent spend on the scheduled load stays ~$8–14/month-equivalent inside the subscription (`crosscut-finance-trading-ai.md §3` calibration), so cross-vendor grading adds roughly 30–120 short read-only Codex runs and ~100–200 Gemini/local utility calls per month — well inside Free/Plus and the 250 RPD key.
