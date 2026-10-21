# Cross-vendor writer slice — Codex as the first non-Anthropic executor (2026-10-21)

> **Status: APPROVED TO BUILD by owner instruction 2026-10-21** ("use other agents to make
> changes on this repo as well as schedule routines using other agents … create a plan for
> polishing it off and then go ahead and implement the plan"). This reverses the 2026-10-05 cut's
> D0 branch A. It reopens three deferred items of
> `docs/superpowers/specs/2026-09-25-multi-model-platform-design.md` §14 — item 1 (the Codex
> executor and its containment), the dispatch half of item 9 (no `ExecSpec` extraction; see §4a),
> and the Anthropic-only slice of item 10 (per-provider quota keys) — and nothing else. Branch:
> `multi-model/cross-vendor-writer`, merged with `origin/main` at `1da5144`. Not pushed; pushing
> `origin/main` triggers the deploy autopilot, so the push and deploy are the owner's call.
>
> **Plan style.** Task-level, deliberately: the 2026-09-25 P0 plan ran to 11,404 lines of inlined
> code and tests and was judged too large to execute. Here each task names its files, its named
> tests, its acceptance check, and the old-spec section that holds the reviewed detailed design.
> The implementer writes the code test-first; a reviewer reads the diff before it is committed.

## 1) Aggregated state — done, planned, in progress

| | What | Where |
|---|---|---|
| **Done** | 28 fact-checked vendor docs + matrix (Codex: `chatgpt-openai.md` §3, §7) | `docs/research/llm-landscape-2026-09/` |
| Done | Full multi-model design, 3 adversarial review rounds; executor, containment, gate and JSONL-mapping designs | old spec §2.4, §2.6 (table + `EnvScrubber` contract), §5.3 belt 3b, §9 P4, Review log rounds 1–3 |
| Done | 21-task Phase-1 plan for observability (notify outbox, origin, capture, redactor, settings refusal) | `docs/superpowers/plans/2026-09-25-multi-model-platform-p0.md` — **not a dependency of this slice** |
| Done | Codex login on the Mini, `~/.codex/auth.json`, 2026-10-17, **ChatGPT Free** (`chatgpt_plan_type: free`, no active subscription) | `codex login status` → "Logged in using ChatGPT" |
| Done | Codex CLI present: `codex-cli 0.162.0-alpha.17.2`, bundled in the ChatGPT app, **not on PATH** | `/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex` |
| Done (2026-10-21) | Two headless probes on the Free login; real JSONL event schema recorded; `TASK_COMPLETE:` survives via `-o`; stdin must be closed or `exec` blocks | `tests/fixtures/codex/{ok,command_and_file}.jsonl` |
| **Planned, zero code** | Everything in the old spec and both plans. `grep -r 'resolved_provider\|codex' src/` is empty | — |
| **In progress / overdue** | Haiku 4.5 retirement swap (window opened 2026-10-15; still served on the 16th; 7 pins live, two on the router and learning classifier which fail open) | T0 below |
| Not started | Observability Phase 1 (the 10-05 cut's project of record) | unchanged by this slice; §9 |

## 2) What this slice delivers

After merge and the owner's switch flip:

- `/task --model=codex/gpt-6-luna fix the flaky test in pickem` runs **in a per-job workspace clone under Codex's own Seatbelt**, its commands and messages land in the job's audit log and Telegram stream exactly like a Claude job, Anthropic reviews the resulting diff **before** anything reaches a canonical repo, the runner commits with a provenance trailer and ff-syncs only on LGTM, and the done DM says which provider ran.
- A skill may declare `model: codex/<id>`; a schedule row may carry `{"model": "codex/<id>"}` in its payload (the scheduler already passes payload through, `session.py:699-700`). That is "schedule routines using other agents".
- Codex rate limits pause only the Codex lane; Anthropic's global pause is untouched.
- `ROUTER_PROVIDERS_ENABLED=anthropic` (default) refuses every non-Anthropic job fail-closed, so this merges and deploys safely before the owner flips it.

Not delivered, by design (§9): graders, critics, dissent, redacted projections, the provider ladder, free HTTP lanes, the executor-seam refactor, the dedicated unprivileged user (T8/owner), `code-server` routing (default off — D-A).

## 3) Decisions taken in this plan (defaults chosen; owner may override)

| | Decision | Default here | Why |
|---|---|---|---|
| D-A | May Codex write to **this** repo (`code-server`: server-patch, new-skill, deploys)? | **Off** — `ROUTER_CODE_SERVER_PROVIDERS=anthropic`; mechanism built, flip is one setting + the MISSION/SYSTEM wording in T8 | The review gate is one Anthropic session's judgement; `guards.py` and `lint_docs.py` are what an injected diff targets; INV-21 un-pin is a protected-path change |
| D-B | ChatGPT tier | **Free** (as logged in). Probes work; capacity is "explore"-class | Measure the skip/rate-limit rate on the canary before paying for Plus (old spec D5) |
| D-C | Read-side containment (Seatbelt confines writes and network, not reads — round-1 critical #2) | Executor supports `CODEX_RUN_AS_USER`; **unset by default**; residual stated in §6 | User creation + sudoers is owner work; `code-server` stays off until it is set |
| D-D | Protected-path edits (lint rules, `guards.py` deny names, SYSTEM.md INV-21 row) | **Separate commit, not merged** (T8) | INV-4: protected paths need explicit owner approval; the slice's tests enforce the same rules without them |

## 4) Design deltas versus the old spec (the gap fills)

a. **No `ExecSpec` extraction.** `_build_options` has zero tests; a byte-identical refactor behind a replay gate was the expensive part of the old P3. Instead: one dispatch branch in `run_session` after skill/cwd/isolation/workspace resolution and system-prompt assembly — `if provider != "anthropic": result = await codex_cli.run(...)` — sharing the `job_started` / marker-parse / summary / `job_completed` path. The seam can be extracted later from two working implementations.
b. **The runner commits and pushes; Codex never holds git credentials.** Codex edits files in the clone. After LGTM the runner stages everything, commits with trailers `Executor: codex/<model>` and `Job: <id>`, then `sync_canonical` (`workspaces.py:247`) as today. No `publish.py`, no deploy key. If the job committed on its own, the diff is `git diff <base>` plus the index and working tree.
c. **Binary discovery.** `settings.codex_bin` → `shutil.which("codex")` → the ChatGPT.app bundle path. Launchd's PATH is frozen (state map §2.8), so the bundle path is the realistic default on prod.
d. **`stdin=DEVNULL`, always.** `codex exec` reads a piped stdin as additional instructions and blocks until EOF (probe #1 hung 90 s).
e. **`--ignore-user-config` always, plus explicit `-c` overrides.** The owner's `~/.codex/config.toml` carries a computer-use `notify` hook and app plugins; none may run under a server job.
f. **One credential, one stream.** This slice uses `settings.codex_home` (default `~/.codex`, the existing login) with `codex` concurrency fixed at 1 — refresh-token rotation makes concurrent streams on one `auth.json` a lockout risk (round-1 major #8). A dedicated stream home is an owner action (§7).
g. **Held jobs go to the tail.** A job whose provider is paused is requeued to the tail with `job_held{provider, reason, until}`; Anthropic keeps INV-12 front-requeue unchanged. Documented exception, tested.
h. **Prompt, not `AGENTS.md`.** The system prompt (directive + job id + marker protocol + transcript + skill body) is prepended to the prompt string. Writing `AGENTS.md` into the clone would be committed by the job and pushed to canonical repos.
i. **Final text of record = the `-o` file**, fallback the last `agent_message`. The marker protocol (`session.py:405-460`) runs on it unchanged.

## 5) Tasks — in this order, one commit each, reviewer before every commit

Every task: tests first (pure/fixture style, no network, no live SDK or CLI), `pipenv run pytest -q` green, `python scripts/lint_docs.py` clean, CHANGELOG entry for each module touched (pre-commit hook enforces for `src/`), no protected path edited (T8 excepted, and T8 is never merged by this slice).

### T0 — Haiku 4.5 retirement (overdue; standalone, ships first)
- **Files**: `src/config.py` (+`utility_model: str = "claude-sonnet-4-6"`, `utility_effort: str = "low"`), `src/runner/llm_router.py:148`, `src/runner/learning.py:258`, `src/gateway/telegram_bot.py:132-133` (aliases → sonnet), `src/gateway/web.py:691` (drop option), `src/runner/session.py:467` (budget row), `skills/project-update-poll/SKILL.md:4`, `skills/TEMPLATE.md:15`, `skills/README.md:12`, `tests/test_pure_functions.py:143`.
- **Tests**: no literal `claude-haiku-4-5-20251001` remains under `src/` or `skills/*/SKILL.md` (grep test); router and learning options carry `settings.utility_model` + effort low; alias table has no haiku key; `test_skill_contracts` green for all 72 skills.
- **Accept**: swap complete; the two fail-open classifiers no longer depend on a model whose retirement window is open.
- **Implemented 2026-10-21** (uncommitted, awaiting reviewer). Two notes against the section as written: (1) "aliases → sonnet" and "alias table has no haiku key" were both honoured by moving `haiku`/`haiku-4-5` out of `_MODEL_ALIASES` into a new `_RETIRED_MODEL_ALIASES` that `parse_flags` consults second — `VALID_MODELS` loses the retired id, and `--model=haiku` still resolves to sonnet rather than passing the bare string through. (2) `test_skill_contracts[project-update-poll]` is green against this tree but reads skills from `settings.skills_dir`, which the dev `.env` points at production, and `pipenv run` re-loads `.env` over the shell; it reports prod's still-Haiku skill until this commit is deployed unless run as `PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest -q -p no:cacheprovider` (1500 passed, 1 skipped). Tests: `tests/test_haiku_retirement.py` (11) + `tests/test_pure_functions.py:143` updated. Docs touched beyond the Files line: `.context/SKILLS_REGISTRY.md`, `.context/SYSTEM.md`, runner/gateway `CONTEXT.md`, `.context/modules/runner/skills/GOTCHAS.md`.
- **Review applied 2026-10-21** (verdict changes_requested → lgtm): note (2) above is superseded — `registry.skills.load`/`list_all` take an optional `skills_dir`, `tests/test_skill_contracts.py` passes the repo's own `skills/`, and the plain `pipenv run pytest -q -p no:cacheprovider` is green from the dev checkout (1500 passed, 1 skipped). The two `llm_route` tests patch `src.registry.skills.list_all` so the catalog build never touches the filesystem. `.claude/settings.local.json`'s unrelated working-tree hunk was left unstaged. Registry CHANGELOG/CONTEXT updated for the new parameter.

### T1 — Models registry and provider-qualified ids
- **Files**: new `src/registry/models.py`, `models.yml` (repo root; anthropic ids + aliases + context windows as today; codex `gpt-6-luna`, `gpt-6-sol`, `gpt-6-astra` from `chatgpt-openai.md` §1); `src/registry/skills.py` (`SkillConfig.provider`, `.model_id` derived; `model` stays the raw string so `test_agents.py:33-56` and `test_registry_failclosed.py:58-61` pass); `telegram_bot._MODEL_ALIASES`, `web.py` dropdown, `session._MODEL_BUDGETS` fed from the registry; `tests/test_skill_contracts.py:24` imports `VALID_MODELS` from the registry; `src/config.py` (+`router_providers_enabled: str = "anthropic"`, `router_code_server_providers: str = "anthropic"`, `codex_bin: str = ""`, `codex_home: str = ""`, `codex_sandbox_default: str = "workspace-write"`).
- **Design**: old spec §2.5 (`[provider/]model_id`, bare → `anthropic/`, unknown provider or model fails the job — C12 fail-closed, never a default).
- **Tests**: `tests/test_models_registry.py` — parse table, alias resolution, unknown provider raises `ProviderRefused`, every one of the 72 frontmatters and 31 escalation targets resolves, `VALID_MODELS` equals today's set plus the codex ids.
- **Carried from T0 review (2026-10-21)**: `POST /api/jobs` copies `req.model` into `payload["model"]` unvalidated (`web.py` ~388) and `session.py` (~698) hands any payload model straight to the SDK, so a stale client can still submit `claude-haiku-4-5-20251001` after T0's dashboard swap. T1's registry validation must cover the web request and the job-payload paths (`ProviderRefused` on unknown ids), not only `telegram_bot.parse_flags`; add a test that posts the retired id and expects a 4xx / failed job.

### T2 — Migration 007-lite
- **Files**: `alembic/versions/007_provider_columns.py` (revises 006; additive, nullable: `jobs.resolved_provider` s32, `jobs.terminal_reason` s32, `jobs.model_served` s64; backfill `resolved_provider='anthropic'` where `resolved_model LIKE 'claude-%'`), `src/models.py`, `tests/test_migrations.py` (chain ends at 007; `jobs.status` CHECK untouched).
- **Accept**: `alembic upgrade head` + `downgrade -1` round-trip in the migration test's SQLite/pg fixture pattern.

### T3 — The Codex executor
- **Files**: new `src/runner/executors/__init__.py`, `src/runner/executors/codex_cli.py`; fixtures `tests/fixtures/codex/ok.jsonl`, `tests/fixtures/codex/command_and_file.jsonl` (recorded 2026-10-21 on 0.162.0-alpha.17.2), `tests/fixtures/codex/file_change_and_failure.jsonl` (hand-authored from `chatgpt-openai.md` §7 for `file_change`, `reasoning`, `web_search`, `turn.failed` — labelled as such in the file header).
- **Contract**: `async def run(job, *, cwd, prompt, model_id, sandbox, timeout_s, on_event) -> ExecResult` where `ExecResult = {final_text, usage, terminal_reason, model_served, thread_id, cli_version}`; `interrupt(job_id)` sends SIGTERM then SIGKILL after 1.5 s (INV-8).
- **Invocation** (flags verified on the bundled build): `<codex_bin> exec --json --ephemeral --ignore-user-config --skip-git-repo-check --sandbox <mode> -C <clone> -m <model_id> -c features.goals=false -c analytics.enabled=false -c otel.metrics_exporter="none" -c sandbox_workspace_write.network_access=false -o <jobdir>/codex-last.md "<prompt>"`, `stdin=DEVNULL`, env from `scrubbed_env()`.
- **`scrubbed_env()`**: exactly `{PATH, HOME, LANG, TMPDIR, CODEX_HOME}`; a test asserts none of `ANTHROPIC_*`, `CLAUDE_CODE_OAUTH_TOKEN`, `TELEGRAM_*`, `DATABASE_URL`, `POSTGRES_*`, `REDIS_URL`, `WEB_AUTH_TOKEN`, `ALPACA_*`, `TRADIER_*`, `FINNHUB_*` survives (old spec §2.6 contract). `CODEX_RUN_AS_USER` set → argv is prefixed `sudo -n -u <user> --`.
- **Event mapping** (old spec §2.4; verified shapes): `thread.started` → audit `executor_started{executor:"codex_cli", thread_id, model, cli_version}`; `item.started/command_execution` → `tool_use{tool_name:"Bash", tool_use_id:item.id, input:{command}}`; `item.completed/command_execution` → `tool_result{tool_use_id, exit_code, output: aggregated_output[:500]}`; `item.completed/agent_message` → `text`; `reasoning` → `thinking`; `file_change` → `tool_use{tool_name:"Edit", input:{path, kind}}` + `tool_result`; `web_search` → `tool_use{tool_name:"WebSearch"}`; `turn.completed.usage` → `{input_tokens, cache_read_input_tokens←cached_input_tokens, cache_creation_input_tokens←cache_write_input_tokens, output_tokens, reasoning_output_tokens}`; `turn.failed`/`error` → `terminal_reason ∈ {rate_limited (429, "slow_down", usage limit), auth_expired (401, "login"), api_error}`; process exit non-zero with no `turn.completed` → `api_error`. Audit kinds and shapes are the existing contract (C14) — same strings `review._summarize_tool_usage`, learning's Write/Edit gate and `retrospective.parse_read_events` already parse. Every event also publishes to `jobs:stream:<id>` like `_handle_message` does.
- **Tests**: `tests/test_codex_executor.py` — argv builder (every flag, sandbox modes, run-as-user prefix), env scrub deny set, mapping on all three fixtures (golden audit-kind sequences), usage mapping, terminal reasons, `-o` file precedence, binary discovery order, timeout → SIGTERM/SIGKILL on a fake process, no network and no subprocess in tests (process factory injected).

### T4 — Dispatch at the single executor call site
- **Files**: `src/runner/session.py` (`run_session`: after isolation + workspace + system prompt, resolve `(provider, model_id)` via the registry with precedence `payload.model > skill.model > settings.default_model`; branch), `src/runner/main.py` (stamp `resolved_provider`, `terminal_reason`, `model_served` on the Job row; `_sanitize_payload`/dispatch MCP strip nothing new — `model` is already honoured), `src/audit_log.py` docstring (new kinds).
- **Fail-closed refusals before any process starts** (audit `provider_refused{provider, reason}` + `job_failed error_category=provider_refused`, no escalation): provider not in `router_providers_enabled`; isolation tier not `workspace`; skill declares `subagents:` or `needs-*-mcp` tags; skill is in the `code-server` set (`server-patch`, `server-deploy`, `new-skill`, `deploy-director`, `atlas-redeploy`, `project-redeploy`) and provider not in `router_code_server_providers`; a `payload.model` override on a job with `origin` other than owner (telegram/web/cli) when the skill pins anthropic.
- **Audit**: `provider_selected{provider, model, reason ∈ pin|payload|default}`; `job_started.provider`; `job_completed{…, provider, model_served, terminal_reason}`.
- **Tests**: `tests/test_provider_dispatch.py` — each refusal path; precedence; the Anthropic path is byte-identical in behaviour (existing session tests untouched and green); fake executor injected.

### T5 — Pre-push Anthropic review gate for non-Anthropic lanes (INV-21(c), closes the ff-sync-before-review hole)
- **Files**: `src/runner/session.py` (`finally` block before `sync_canonical`, `session.py:1038-1043`), `src/runner/review.py` (`run_code_review(parent_job_id, diff, cwd)` reused as-is; a thin `diff_for_gate(cwd, base_sha)` helper covering committed + staged + unstaged), `src/runner/main.py` (`review_outcome` stamp; DM text).
- **Rule, not a switch**: `if provider != "anthropic": gate runs` — no env var can disable it (round-1 critical #1). `asyncio.wait_for(…, 600)`; timeout counts as `changes_requested`.
- **Outcomes**: `lgtm` → runner commits (trailers `Executor: codex/<model>`, `Job: <id>`, `Reviewed-By: anthropic/<reviewer model>`) → `sync_canonical`; anything else → clone kept, no sync, `job_failed error_category=review_blocked`, audit `merge_gate_verdict{belt:"pre_push", reviewer_provider:"anthropic", verdict, findings_n}`, `tasks:notify` failed card naming the verdict. Empty diff → no gate, no commit, job completes (research-class jobs).
- **Tests**: `tests/test_pre_push_gate.py` — gate runs iff provider ≠ anthropic; each outcome; timeout; empty diff; trailer format; `sync_canonical` never called on a non-LGTM (spy).

### T6 — Per-provider quota keys
- **Files**: `src/runner/quota.py` (`pause_provider(provider, reset_at, reason)`, `is_provider_paused(provider)`, `clear_provider`; existing global functions keep their Anthropic meaning and INV-12 semantics), `src/runner/main.py` (`_process_job`: cheap pre-resolution `resolve_provider(job)` via the registry; if paused → `job_held{provider, reason, until}` + `RPUSH` to tail + release slot + continue; on `terminal_reason=rate_limited` from a non-Anthropic executor → `pause_provider` + `LPUSH` front, never the global key), `src/db.py` key constants, `src/gateway/web.py` `/api/quota` (+ per-provider map), `src/gateway/telegram_bot.py` `/status` line per paused provider.
- **Tests**: `tests/test_quota.py` (extend) — provider keys independent of the global key; held → tail requeue with audit; Codex 429 never touches `quota:paused_until`; fakeredis.

### T7 — Surfaces: provider everywhere the owner looks
- **Files**: `telegram_bot.py` (`/jobs` rows and the done/failed DM show `provider/model`; `/task --model=codex/<id>` parses through the registry, unknown → refused at parse time with the reason), `web.py` (jobs table column; model `<select>` from the registry grouped by provider), `audit_index.py` (`provider` in INDEX.jsonl entries).
- **Tests**: `test_telegram_bot.py` (extend: parse_flags with provider ids, DM text), `test_web.py` (dropdown from registry), `test_audit_index.py` (field present, None for pre-007 rows).

### T8 — Protected-path bundle (separate commit on `multi-model/protected-bundle`; **not merged by this slice**)
- **Files**: `scripts/lint_docs.py` (rules: non-Anthropic provider ⇒ `isolation: workspace`; provider and model must exist in `models.yml`; `code-server` skills must resolve to anthropic unless `router_code_server_providers` lists the provider — read from the same registry so the pin cannot be relaxed from yml alone), `src/runner/guards.py` (deny assignment/export of `OPENAI_API_KEY|CODEX_API_KEY|GEMINI_API_KEY|OPENROUTER_API_KEY|XAI_API_KEY|CLAUDE_CODE_OAUTH_TOKEN` beside `ANTHROPIC_API_KEY` at `:148-149` and `:261-262`; broker-host deny `api.tradier.com|sandbox.tradier.com/v1/accounts/*/orders|*.alpaca.markets/v2/orders` in the hard-deny list `:137-149` — the open INV-22 server-side follow-up), `.context/SYSTEM.md` INV-21 row (implemented profile: workspace-only, Seatbelt, scrubbed env, no MCP, pre-push Anthropic gate, provider keys; `code-server` pinned by setting), `MISSION.md` untouched (its non-goal wording stays true while D-A is off).
- **Tests** ride the same commit: `tests/test_guards.py` extensions, `tests/test_doc_lint.py` wiring for the three rules.
- The owner reviews the diff and merges it themselves (INV-4 protected paths). Until then, the slice's own tests enforce the lint rules (T1/T4 tests) and the env scrub (T3) — the guard additions are belt-and-braces.

### T9 — Docs, registries, runbook
- CHANGELOGs (runner, gateway, registry, db); `.context/modules/runner/CONTEXT.md` (Paths line + `executors/` + public interface), `registry/CONTEXT.md`, `db/CONTEXT.md`; `.context/SYSTEM.md` module-graph rows (`src/runner/executors/codex_cli.py`, `src/registry/models.py`); `.context/INDEX.md` + `docs/README.md` rows for this plan; `docs/TROUBLESHOOTING.md` symptoms (`provider_refused` reasons; `review_blocked`; "codex exec hangs" → stdin; "codex not found" → `codex_bin`; `auth_expired` → `codex login --device-auth`); the owner runbook (§7) as a section of this plan kept current; the old spec's §14 items 1/9/10 annotated "reopened 2026-10-21 by this slice".

### T10 — Live canary (last; needs the owner-provided login; the dev runner is never started)
- `scripts/codex-canary.sh`: clones a throwaway repo into the scratch area, invokes `python -m src.runner.executors.codex_cli --canary <clone>` which runs a real `codex exec` with the slice's argv and env, asserts: `executor_started`/`tool_use`/`tool_result`/`text`/`turn.completed` kinds in order, `TASK_COMPLETE:` in the final text, a file written inside the clone and nothing outside it, no `ANTHROPIC_*` or `TELEGRAM_*` key visible to the child (a `env` command in the prompt whose output is checked), exit 0. Then `--gate-dry-run` feeds the clone's diff through `review.run_code_review` on Anthropic and prints the verdict without syncing.
- Records the measured wall time, tokens and whether the Free plan rate-limited, into this plan's §8.

## 6) Containment — what holds, what is residual

Holds: per-job clone (INV-16); Codex Seatbelt `workspace-write` with network off (writes confined to the clone); scrubbed env (no server, vendor, broker or Telegram secrets reach the child; `env_files` is never applied for non-Anthropic executors — test); no MCP, no subagents (capability refusal); Anthropic reviews every diff before it can reach a canonical repo and the runner is the only committer/pusher; kill switch default off; `code-server` off by default.
Residual (D-C): Seatbelt does not confine reads, so a prompt-injected Codex job could read owner files by absolute path and echo them into model context. `CODEX_RUN_AS_USER=_aicodex` with a sudoers rule removes it; until the owner provisions that, keep Codex off `code-server` and off any skill whose clone carries secrets (none do without `env_files`, which this lane never gets).

## 7) Owner actions (auth config, sudo, or policy — never done by a job)

1. **Flip the switch** when ready: `ROUTER_PROVIDERS_ENABLED=anthropic,codex` in prod `.env`; restart runner + bot.
2. **Dedicated Codex stream home** (recommended before scheduled use; optional for the canary): `CODEX_HOME=~/Library/Application\ Support/ai-server/volumes/codex/stream-0 /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex login --device-auth`, then `CODEX_HOME=…/stream-0` in `.env`. Turn "Improve the model for everyone" off in ChatGPT settings before any repo content goes through (`chatgpt-openai.md` §3).
3. **Tier**: stay Free for the canary; decide Plus $20 on the measured rate-limit rate (§8).
4. **Read-side containment** (optional, unlocks `code-server`): create `_aicodex`, a sudoers line for the fixed argv, set `CODEX_RUN_AS_USER=_aicodex`; the executor's tests already cover the prefix.
5. **Protected bundle**: review and merge `multi-model/protected-bundle` (T8).
6. **`code-server`** (optional, after 4 and 5): `ROUTER_CODE_SERVER_PROVIDERS=anthropic,codex` and the matching MISSION §non-goals wording edit, together.
7. **Deploy**: push `origin/main` (autopilot) or `/task deploy server`.

## 8) Verification gates

Per task: named tests green, full suite green (baseline 1489 passed), lint clean, reviewer LGTM recorded in the commit message trailer `Reviewed-By:`. Whole branch: a fresh reviewer over `git diff main...` for correctness, safety (the §6 list, item by item), and docs. Canary (T10): recorded here when run.

| Canary | result |
|---|---|
| wall time / tokens / rate-limited? | _(filled by T10)_ |
| audit-kind sequence matched | _(filled by T10)_ |
| secrets visible to child | _(filled by T10)_ |
| gate verdict on the canary diff | _(filled by T10)_ |

## 9) Out of scope / deferred (one line each)

Graders, critics, dissent, redacted projections — old spec §14 items 6–8. Provider ladder and scoreboard — item 7. Free HTTP utility lanes (Gemini, Cerebras, Groq) — item 2. `ExecSpec` extraction — item 9, reopens when a third executor exists. Remote MCP front door — item 12. Observability Phase 1 (outbox, origin, cost columns) — the 10-05 spec, unchanged and still the better next investment after this slice. Other agent CLIs (Antigravity `agy`, Kiro, Cursor, Copilot, Grok Build) — the executor module's contract (T3) is the adapter shape; each needs its own fixture set and terms check before a second module is written.
