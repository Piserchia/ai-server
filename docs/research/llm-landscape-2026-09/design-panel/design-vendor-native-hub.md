# Design: Vendor-native hub — the server as aggregator, ledger, review gate and dashboard

Architect lens: *let each vendor's own scheduled agents do the work on the vendor's side; ai-server subscribes to and collects the results, stores them in one ledger, shows them on one board, and executes only Anthropic-pinned work itself.* Date 2026-09-24. Citations: `R:<doc> §n` = `docs/research/llm-landscape-2026-09/<doc>.md`; `M:§n` = the current-state map; `file:line` = repo paths from the state map.

## 0) Thesis

The server already has a vendor-neutral, load-bearing *lifecycle protocol* around a single Anthropic executor: Job row + Redis queue, per-job JSONL audit log, the text-marker deliverable contract, workspace-clone containment, the in-session Anthropic review gate, and out-of-band Telegram alerters (`M:§1` "three structural facts"; `M:§6`). What it lacks is a provider dimension, cost/quota visibility, and any surface that shows deliverables (`M:§5`). Instead of teaching the Mac Mini to *run* Codex, Gemini, Grok and Perplexity — which needs a second containment layer per vendor (INV-21b), more RAM on a 16 GB box (`M:§2.8`), and executor adapters for JSONL dialects that churn weekly (`R:crosscut-subscription-automation-tos §5.3`) — this design keeps the box Anthropic-only and turns it into the **hub**: a tracked *vendor schedule registry* declares what should run where; vendor-side scheduled agents (Claude Routines, Jules, Codex cloud tasks, ChatGPT/Grok scheduled tasks) execute on the vendor's infrastructure; **collectors** (GitHub webhooks/polling, Jules API, IMAP, vendor quota pollers, an OTLP receiver) pull results into a new `vendor_runs`/`artifacts` ledger; the existing Anthropic `code-review` gate and `_evaluate` lanes judge every external deliverable before it merges or is trusted; and one Fleet board (web + `/fleet` on Telegram) shows schedule adherence, quota per vendor, queued/blocked/late runs and deliverables. Honest limit stated up front: **only three vendor-native surfaces can be both triggered and collected headlessly today** — Claude Routines (`/fire` API + GitHub PRs), Google Jules (`v1alpha` API + auto-PR) and Codex cloud tasks (GitHub PRs); ChatGPT and Grok scheduled tasks egress only by email; Gemini Scheduled Actions have no egress at all; Perplexity's consumer surfaces are ToS-banned for anything scripted. The design therefore treats GitHub and the owner's mailbox as the two universal sinks, keeps every credential-bearing Atlas loop on the box, and is explicit about where visibility degrades to "the vendor's own app".

## 1) Architecture

### 1.1 Components (text diagram)

```
                 VENDOR SIDE (their schedulers, their VMs, their quota)
 ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐ ┌─────────────────┐ ┌────────────────┐
 │ Claude Routines  │ │ Google Jules │ │ Codex cloud tasks│ │ ChatGPT sched.  │ │ Grok Automat.  │
 │ cron≥1h,/fire,   │ │ API v1alpha  │ │ @codex on PRs,   │ │ tasks (RRULE)   │ │ (daily/weekly, │
 │ GitHub triggers  │ │ AUTO_CREATE_PR│ │ codex cloud exec │ │ push/email      │ │ email egress)  │
 └───┬─────────┬────┘ └──┬───────┬───┘ └───────┬──────────┘ └────────┬────────┘ └───────┬────────┘
     │PRs      │run id   │PR     │poll          │PRs                  │email             │email
     ▼         ▼         ▼       ▼              ▼                     ▼                  ▼
 ═══ GitHub (canonical repos: Piserchia/atlas, project repos) ═══   ═══ owner mailbox (IMAP) ═══
     │ webhook (HMAC) + gh poll                                        │ label-filtered poll
     ▼                                                                 ▼
 ┌──────────────────────────────── ai-server (Mac Mini, Anthropic-only executor) ───────────────────────────┐
 │  src/collectors/   github.py  jules.py  imap.py  quota.py (codex app-server, claude probe, jules count)  │
 │                    otlp.py (OTLP-HTTP receiver route in web.py; Claude Code + Codex emit natively)      │
 │        │ normalise → vendor_runs / artifacts / quota_snapshots (Postgres) + vr-<id>.jsonl (audit_log)   │
 │        ▼                                                                                                │
 │  src/hub/registry.py   vendor-schedules.yml (tracked) ─► adherence (extends schedule_adherence.py)     │
 │  src/hub/fire.py       ScriptExecutor jobs: routine-fire, jules-create, codex-cloud-exec (no LLM)       │
 │        │ deliverable arrives                                                                            │
 │        ▼                                                                                                │
 │  EXISTING runner (main.py:376 → session.run_session) — Anthropic-pinned lanes only:                    │
 │     pr-review (code-review subagent, INV-13/INV-4)  _evaluate  server-patch/deploy  atlas-* loops      │
 │        │ merge_gate_verdict stored on artifact                                                          │
 │        ▼                                                                                                │
 │  gateway: Telegram /fleet /runs /fire /quota /deliverables + cards ; web Fleet board (static app, SSE)   │
 └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 What stays exactly as it is

- The single executor call site `main.py:376-380` → `session.run_session` (`session.py:864`) and its `ClaudeAgentOptions` build (`session.py:650-816`) are untouched. No Codex/Gemini/Grok CLI executor is added to the box (this is the deliberate difference from the "executor abstraction" lens). INV-3 (`main.py:77-84`, `guards.py:148-149,261-262`) is unchanged.
- Job/Task/Schedule/Proposal models (`models.py:82,138,206,230,264`), `enqueue_job` (`jobs.py:16-47`), Redis contracts (`db.py:44-55`), the JSONL audit log and marker protocol (`session.py:405-460,1005-1017`), workspace clones (`workspaces.py:127-170,247-270`), guard hooks (`guards.py:381-490`), the review gate (`review.py:247-256`; `skills/code-review/SKILL.md`), the scheduler loop (`main.py:1327-1362`) and the out-of-band alerters (`scripts/healthcheck-all.sh`, `ops/heartbeat-worker`) all stay.

### 1.3 Data model changes (migration 007)

| Table / column | Purpose | Notes |
|---|---|---|
| `vendor_runs` (id, vendor ∈ {anthropic-routine, google-jules, openai-codex-cloud, openai-chatgpt-task, xai-automation, github-copilot-automation, cursor-automation}, surface, registry_key, external_id, trigger ∈ {vendor-cron, server-fire, github-event, manual}, fired_by_job_id NULL, expected_at, observed_started_at, observed_finished_at, status ∈ {expected, fired, observed, delivered, late, missing, failed, ignored}, quota_snapshot_id, raw JSONB) | one row per expected or observed vendor-side run | `expected` rows are created by the registry (§4) so "missing" is computable; observed-only rows (a Routine the owner fired from the phone) get `registry_key NULL` |
| `artifacts` (id, vendor_run_id NULL, job_id NULL, kind ∈ {pr, commit, email, file, api_result, session_link}, locator (PR URL / message-id / path / run id), sha256, title, body_excerpt, schema_ok BOOL, merge_gate_verdict ∈ {lgtm, changes_requested, error, n/a}, review_job_id, delivered_to_owner_at, owner_action ∈ {approved, rejected, reopened, none}) | the deliverable record that today does not exist (`M:§5` items 10-12) | also populated for *local* jobs: `<job>.summary.md` and files written by skills become `file` artifacts, closing the "deliverables unreachable" gap |
| `quota_snapshots` (id, vendor, window ∈ {five_hour, seven_day, daily, monthly, credits}, used_pct, resets_at, source ∈ {status-line-probe, codex-app-server, jules-count, inferred}, ts) | per-vendor remaining budget | schema from `R:crosscut-subscription-automation-tos §3.10a` |
| `jobs.resolved_provider` (String 32), `jobs.tokens_in/out/cache_read/cache_write` BIGINT, `jobs.cost_usd_est` NUMERIC, `jobs.num_turns`, `jobs.duration_api_ms`, `jobs.terminal_reason` | capture the fields the pinned SDK already exposes and `session.py:1095` drops (`M:§2.1` usage accounting lossy) | `resolved_provider = 'anthropic'` for every local job; the column exists so the scoreboard can join local and vendor runs |
| `schedules.executor` ∈ {local, routine-fire, jules-create, codex-cloud} (default local) + `schedules.registry_key` | lets the existing scheduler loop fire vendor runs on cron | seed script gains an `executor` argument (`scripts/seed-schedules.sh:22-47`) |
| `tasks.origin_channel`, `tasks.origin_ref` (replace the Telegram-only `chat_id`/`thread_message_id` semantics without dropping the columns) | channel-agnostic origin binding so vendor deliverables and web launches get lifecycle cards (`M:§6` "Task.chat_id … Accidental") | |

### 1.4 Executors / providers under this lens

- **Local executor**: Claude Agent SDK only (unchanged). Task classes pinned here: `review-gate`, `_evaluate`, `code-server`, and every Atlas loop that needs `projects/atlas/.env` or the atlas DB (`M:§2.6` credentials; INV-22).
- **`ScriptExecutor` (implements the dead `no_llm` flag, `skills.py:55`)**: three script skills — `routine-fire` (`POST https://api.anthropic.com/v1/claude_code/routines/<id>/fire` with the per-routine bearer + beta header `experimental-cc-routine-2026-04-01`; `R:claude-anthropic §7` "Optional cloud complements"; `R:crosscut-subscription-automation-tos §3.1` Routines), `jules-create` (`POST https://jules.googleapis.com/v1alpha/sessions`, `automationMode: AUTO_CREATE_PR`, `X-Goog-Api-Key`; `R:gemini-google §7`), `codex-cloud-exec` (`codex cloud exec` on plan auth; `R:chatgpt-openai §2` "Codex cloud"). These run as ordinary `jobs` rows (kind = skill name, `created_by='scheduler'`) so they inherit audit, INDEX, cancel and Telegram plumbing, but never spawn the Claude CLI.
- **Vendor-native lanes** (no executor on the box): ChatGPT Scheduled Tasks, Grok Automations, Gemini Scheduled Actions, Claude Routine *cron* triggers, Jules scheduled tasks. The server only *expects* and *collects* them.

### 1.4a Collectors — the aggregator layer (`src/collectors/`)

Each collector is a pure-function normaliser plus a thin I/O loop; all run as one `collector_loop` asyncio task added to the runner's supervision set (`main.py:1419-1486`, today four tasks) and share the runner's crash-restart semantics. None holds an LLM.

| Collector | Source / cadence | Auth | Normalises into | Failure mode & alarm |
|---|---|---|---|---|
| `github.py` | `POST /api/hooks/github` (pull_request, push, check_suite, issue_comment) + `gh pr list --json` poll every 5 min per registered repo as fallback | webhook HMAC secret; `gh` PAT | `vendor_runs.observed` (match by branch prefix `routine/`, `jules/`, `codex/` or PR body marker `Vendor-Run: <key>`), `artifacts{kind: pr}` with head SHA, CI status | webhook 401/replay → dropped + counted; poll drift >15 min → `collector_degraded` DM |
| `jules.py` | `GET /v1alpha/sessions/{id}` + `activities` every 2 min while a session is open; daily count for quota | `JULES_API_KEY` header | run status (`queued/running/awaiting_plan_approval/completed/failed`), PR URL from outputs, `quota_snapshots{window: daily}` | 401 → `auth_expired` card; 429 → back-off + `quota_warning` |
| `imap.py` (H4) | IDLE or 5-min poll on one label (`ai-server/inbox`) in the owner's mailbox | app password, read-only | `artifacts{kind: email}` with `Message-ID`, sender-vendor mapping (`noreply@openai.com` → chatgpt-task, xAI sender → grok-automation), body text, sha256 | parse failure keeps the raw MIME as artifact body; sender not in the map → `ignored` + weekly digest |
| `quota.py` | Claude: a 5-minute interactive probe session whose `statusLine` command appends `rate_limits.*` JSON to `volumes/telemetry/claude_rate_limits.jsonl` (`R:claude-anthropic §3` progress table; not available in `-p`); Codex: one `account/rateLimits/read` over app-server stdio per 15 min (`R:chatgpt-openai §3`); Jules by count; others `inferred` from our own ledger | existing logins | `quota_snapshots` | probe fails → `auth_expired`/`login-expired` card (the `-p` lane gives no 3-day warning, `R:claude-anthropic §3` credential lifecycle) |
| `otlp.py` (optional) | `POST /api/otlp/v1/metrics|logs` FastAPI route (OTLP/HTTP JSON) — Claude Code (`CLAUDE_CODE_ENABLE_TELEMETRY=1`) and Codex `[otel]` both emit natively | loopback only | `agent_events` rows: tokens by model/effort, tool decisions, api errors | no daemon; if the route is off nothing breaks (JSONL remains the source of record) |
| `adherence.py` | every 10 min over `vendor_runs.expected` + local schedules | — | `late`/`missing` flips; feeds `/fleet` badges and the existing 07:15 report (`schedule_adherence.py`) | — |

Common normalised event (one Postgres row, one JSONL line; from `R:crosscut-subscription-automation-tos §3.10a` with our ids): `{ts, lane, auth_mode, registry_key, vendor_run_id, job_id, session_id, kind, model, tokens{in,out,cache_read,cache_write}, cost_usd_est, quota{window, used_pct, resets_at}, artifact_id, error_type}`.

### 1.4b Hub API (all behind the existing web auth, read routes also behind CF Access on the Fleet vhost)

`GET /api/hub/fleet` (registry × latest run × quota), `GET /api/hub/runs?vendor=&status=&limit=`, `GET /api/hub/runs/{id}` (timeline + raw), `GET /api/hub/artifacts?pending=1`, `POST /api/hub/artifacts/{id}/action {approve|reject|followup:text}`, `POST /api/hub/fire {registry_key, text}`, `GET /api/hub/quota`, `GET /api/hub/scoreboard?window=30d`, `GET /api/hub/events/stream` (SSE over `hub:events`), `POST /api/hooks/github`, `POST /api/otlp/v1/{metrics,logs}`. `/health` keeps its stable keys (`M:§3` C23) and gains `hub_collectors_ok`.

### 1.5 Routing / policy

`providers.yml` + `routing-policy.yml` from the approved plan (`docs/superpowers/plans/2026-08-10-model-router.md §6a, §6d`) are adopted verbatim in shape, but the non-Anthropic entries have `kind: vendor-native` instead of `cli-agent`, i.e. the policy decides *which vendor's scheduled agent* gets a task class, not which local binary. Initial pins:

| Task class | Lane | Why |
|---|---|---|
| `code-server` (server-patch, new-skill, deploys) | local Claude | INV-4/INV-21 pin; ai-server repo never given to a vendor agent |
| `review-gate` (code-review subagent, post_review, `_evaluate`, new `pr-review`) | local Claude | C5/C7; verdict now recorded structurally on the artifact |
| `code-project` (atlas build, pickem/bingo patches) | Jules (canary) → Codex cloud (canary) → Claude Routine on the repo (qualified from day 1: same vendor as today) | PR-shaped output; reviewed by `pr-review` before merge (INV-21c) |
| `research-read` (public-data briefs, sector scans) | ChatGPT Scheduled Task (email) → Grok Automation (email, X data) → Claude Routine | owner-only outputs; no theses in prompts |
| `adversarial-review` of committed memos | Codex cloud `@codex` on a review PR → Claude Routine (self-review, different miss set) | independence ranking `R:crosscut-subscription-automation-tos §5.2a`: Codex/GPT-6 high, Gemini high, Grok high; Jules is code-only so not used here |
| `utility-classify` (llm_router, learning) | local Haiku today → local Ollama qwen3.5:4b (plan R1) | unchanged by this lens; `R:local-models-m4-16gb §7` |
| `atlas-*` loops with credentials | local Claude, unchanged | INV-22, `M:§2.6` |

Capability matching keeps MCP/subagent/credential-needing skills local automatically: any skill with `needs-*-mcp` tags, `subagents:`, or a project `env_files` manifest cannot be assigned a vendor-native lane (data lives in the registry, no special-case code — plan §6d).

### 1.6 Containment

Vendor-side runs execute in the vendor's own VM with no access to this box, `.env`, Keychain, Postgres or brokerage endpoints — strictly better isolation than `isolation: none` (48/72 skills, `M:§2.1`) for anything that can be repo-scoped. The server's containment obligations become: (a) **input boundary** — only committed, secret-free repo content and public-data prompts leave the box; `vendor-schedules.yml` entries carry `data_class ∈ {public, owner-private, thesis}` and lint refuses `thesis` on any lane whose data row is not marked OK (`R:crosscut-benchmarks-reviews §7` data-handling matrix; Jules data terms are *not found* → Jules is `public`/code-only); (b) **output boundary** — nothing a vendor produced touches a canonical branch without the Anthropic `pr-review` LGTM recorded on the artifact (INV-13/INV-21c), and merges run through the existing guarded-writer deploy paths; (c) **credential boundary** — the three fire scripts hold only their own tokens (`ROUTINE_FIRE_TOKEN_<name>`, `JULES_API_KEY`, `~/.codex/auth.json`), added to the `guards.py` deny list by name (protected path, owner PR); (d) **webhook boundary** — `POST /api/hooks/github` verifies HMAC and is the only new inbound route; IMAP is outbound-only polling.

### 1.7 Event / audit model

Every collector writes to the existing per-run JSONL (`volumes/audit_log/vr-<vendor_run_id>.jsonl`) using *new* kinds — `vendor_run_expected`, `vendor_run_fired`, `vendor_run_observed`, `vendor_artifact_ingested`, `vendor_quota_snapshot`, `vendor_run_missing`, `merge_gate_verdict` — so `audit_log.py`'s parsing contract (`M:§3` C14) is extended, never renamed. Redis: `hub:events` stream mirrors them for the board's SSE; `jobs:done` semantics untouched. INDEX.jsonl gains vendor runs as rows with `lane` set. Local jobs additionally emit `job_completed` with the newly captured usage fields.

### 1.8 Honest matrix — what each vendor supports headlessly *today*, and what it does to visibility and control

| Vendor-native scheduled surface | Create schedule headlessly | Trigger a run headlessly | Collect result headlessly | Run status / progress by API | Remaining quota by API | Net for this design |
|---|---|---|---|---|---|---|
| Claude Routines | **No** (`/schedule` needs interactive claude.ai login; web UI) | **Yes** (`/fire` bearer, GitHub pull_request/release events) | **Yes** via GitHub PR/commit; transcript web-only | **No** (run id only; history web-only) | **Partial** (status-line JSON from an interactive probe, not `-p`) | fire + collect; status = artifact |
| Google Jules | **Yes** (API sessions; scheduled tasks pause/resume) | **Yes** | **Yes** (PR + activities API) | **Yes** (session/activities polling) | by count (published caps) | the cleanest lane; code-only |
| Codex cloud tasks | partial (`codex cloud exec`; scheduled tasks via app) | **Yes** (`codex cloud exec`, `@codex` PR comment) | **Yes** via GitHub PR | **No** documented poll for cloud tasks; local `exec --json` only | **Yes** (`account/rateLimits/read` + `updated`) | fire + collect + best quota read |
| ChatGPT Scheduled Tasks | No (app) | No | **Email/push only** | No | No | email lane, owner-gated |
| Grok Automations | No (app; paid) | email-triggered runs exist | **Email only** | run history in app | No (Settings → Usage UI) | email lane, optional seat |
| Gemini Scheduled Actions / Spark | No | No | **None** (unread chat + push) | No | No | vendor-app-only |
| Grok Bot / Perplexity Computer | No | No (Computer: email trigger) | No / app | No | No | not used |
| Copilot Automations / Agentic Workflows | Yes (workflow files in repo) | Yes (Actions dispatch) | Yes (PRs, run logs) | Yes (Actions API) | credits only | optional, GitHub-native |
| Cursor Automations / Cloud Agents API | Yes (REST) | Yes | Yes (SSE, artifacts endpoint) | Yes | No plan pool number | optional, best API, extra seat |

What this does to **visibility**: progress becomes *artifact-grained* (fired → PR/email arrived → verdict) rather than tool-call-grained; the board can show "running at vendor since 09:31, expected by 12:31" but not what the agent is doing; the two vendors with an API (Jules, Cursor) are the exception. Quota visibility is *better* than today for Codex (RPC), equal for Claude (probe), and inferred for the rest. What it does to **control**: the server can start, ignore, review and gate-merge, but cannot cancel a Routine mid-run, cannot stop a vendor-side cron, and cannot enforce INV-17/INV-20 hooks inside a vendor VM — containment there is the vendor's sandbox plus our input boundary (§1.6). That trade is acceptable for repo-scoped and public-data work and unacceptable for anything credential-bearing, which is exactly the split in §1.5.

## 2) Interfaces & visibility

### 2.1 Telegram (phone) — the commands the owner actually gets

| Command / card | Behaviour |
|---|---|
| `/fleet` | One card: per vendor → last observed run, next expected, adherence badge (OK / LATE / DARK / NEVER_RAN, reusing `schedule_adherence.py` states), quota bar (`used_pct` + reset), unread deliverables count. Buttons: `Runs`, `Deliverables`, `Pause <vendor>`. |
| `/runs [vendor] [n]` | Last n vendor runs + local jobs interleaved by time, status glyphs, artifact links. |
| `/fire <registry_key> [text]` | Enqueues a `routine-fire` / `jules-create` / `codex-cloud-exec` job; the optional text becomes the Routine's `<routine-fire-payload>` (`R:runtimes-aggregators §3` Cloud Routines) or the Jules prompt suffix. Reply carries the run id and a "watch" button. |
| `/deliverables` | Inbox of artifacts awaiting owner action: PR title + review verdict + `Approve merge` / `Reject` / `Ask follow-up` buttons (follow-up = new Jules session or Routine fire with the owner's text). Email artifacts show subject + 600-char excerpt + `Open` deep link. |
| `/quota` | All vendors: Claude 5h/7d used %, Codex primary/secondary `usedPercent` + `resetsAt`, Jules tasks used/15 or /100 today, Copilot credits if enabled; local Ollama load. Red rows when a window is >80 %. |
| `/review <artifact>` | Dispatches `pr-review` (Anthropic, read-only, workspace) on an external PR now instead of waiting for the webhook-triggered one. |
| `/pause <vendor>` / `/resume <vendor>` | Stops server-side firing and marks vendor-side crons `ignored` (honest limit: the server cannot stop ChatGPT/Grok/Gemini/Routine *vendor-side* crons; the card says so and links the vendor page). |
| Cards pushed | `vendor_run_missing` (expected run not observed by `expected_at + grace`), `deliverable_ready` (PR/email landed + verdict), `quota_warning` (>80 % / reset), `auth_expiring` (T-7 d OAuth, T-30 d setup-token; `R:crosscut-subscription-automation-tos §3.10c`). Existing ghost commands (`/rate`, `/status <prefix>`, `/cancel <prefix>`, `M:§5` item 13) are either registered or removed in the same pass. |

### 2.2 Laptop — web Fleet board (replaces the inline-HTML dashboard page for this scope)

Static app under `static/fleet/` behind CF Access (the dashboard vhost is currently app-token only, `M:§2.3` Caddyfile:36-38), consuming `/api/hub/*`:

- **Fleet grid**: rows = registry entries; columns = vendor, cadence, last/next, adherence, last artifact, verdict, cost/quota share. Click → run timeline (expected → fired → observed → delivered) with the raw vendor payload.
- **Live lane**: the existing SSE (`web.py:600-640`) finally rendered for local jobs; vendor runs show a "progress unavailable — vendor app" pill with a deep link (claude.ai/code/routines, jules.google, chatgpt.com/codex) because no vendor exposes run progress by API (`R:crosscut-subscription-automation-tos §3.10`: Routines "web dashboard only; `/fire` returns run id").
- **Quota strip**: per-vendor gauges from `quota_snapshots`; local Anthropic gauge from the status-line probe session (`R:claude-anthropic §3` `rate_limits.five_hour/seven_day`), Codex from `account/rateLimits/read` (`R:chatgpt-openai §3`), Jules by count, everything else `inferred`.
- **Deliverables inbox** with the same approve/reject/follow-up actions as Telegram, plus diff viewer for PRs (`gh pr diff` cached server-side).
- **Cost panel**: subscription fixed costs (owner-entered) + metered `cost_usd_est` per lane + the calibration facts (measured job ≈ 100k in / 82 % cache / 2k out; whole scheduled load ≈ $8-14/mo if metered; `R:crosscut-finance-trading-ai §3` "Empirical calibration") so the owner can see whether a seat is earning its keep.

### 2.3 Vendor apps as first-class surfaces

The lens accepts that the owner will *also* watch runs in the vendors' own apps: Claude Code mobile/web routines list, ChatGPT app task history + push, Grok run history + email, Jules web. The server's job is to make sure every such run also exists in the ledger (observed via GitHub/email/API) so nothing is *only* in a vendor app. Where a vendor run cannot be observed at all (Gemini Scheduled Actions, Grok Bot), the registry entry is `visibility: vendor-app-only` and the board renders it grey.

### 2.4 CLI (laptop terminal)

`python -m src.hub.cli fleet|runs|fire|quota|deliverables` reusing the same API; owner terminal work stops appearing as ad-hoc `created_by` strings (`M:§2.3`).

### 2.5 What "watch their progress" looks like — one task, end to end

1. **09:02 phone** — owner: `/task fix the stale SGOV fallback in atlas trader --lane=jules`. Bot ack within 2 s: "Queued as job `7f3a…` → lane `google-jules` (code-project canary). Watch: `/runs 7f3a`." A Task row is created with `origin_channel=telegram` so every later card threads under this message (`telegram_bot.py:267-270` pattern generalised).
2. **09:02 server** — `jules-create` script job runs (no LLM, <5 s), posts the session with `AUTO_CREATE_PR`, writes `vendor_runs{status: fired, external_id: sessions/abc}` and audits `vendor_run_fired`. Card: "Jules session `abc` started · expected PR by 12:02 · quota 3/15 today."
3. **09:02–09:40 vendor** — Jules plans and works in its VM. `jules.py` polls every 2 min; the board's run timeline shows `awaiting_plan_approval` → `running` (if `requirePlanApproval` is on, a `Approve plan` button appears — the only mid-run control this lane offers).
4. **09:41 GitHub → server** — `pull_request.opened` webhook → `artifacts{kind: pr, locator: Piserchia/atlas#412}` → `pr-review` job enqueued (local Claude, workspace clone of the PR head, read-only, `code-review` subagent). Card: "PR #412 landed from Jules · Anthropic review running."
5. **09:47 server** — `pr-review` finishes; `merge_gate_verdict=changes_requested` with two findings. Card with `Ask follow-up` (pre-filled with the findings) / `Reject` / `Approve anyway (owner)`. Owner taps `Ask follow-up`; the same Jules session receives the findings (`POST …/sessions/abc:sendMessage` or equivalent activity), `vendor_runs` gets a child row.
6. **10:05** — new commits; webhook `synchronize` → review re-runs → `lgtm`. Card: "PR #412 LGTM · protected paths: none · `Approve merge`?" (execution lane could auto-merge; the canary ladder keeps the button while the lane is `canary`).
7. **10:06** — owner taps `Approve merge` → `pr-merge` guarded-writer job squashes → `atlas-redeploy` dispatched through the existing gated path → healthcheck green → card: "Deployed 10:11 · trader healthcheck OK · artifact chain: ask → Jules `abc` → PR #412 → review `9c1e…` → merge → deploy `b77d…`." `/fleet` shows the Jules row `OK · 4/15 today`.
8. **Laptop, any time** — the Fleet board shows the same chain as one line with the raw Jules activity log, the PR diff, the review findings and the deploy job's SSE stream.

The same shape holds for a Routine (step 2 = `/fire`; step 3 = "running at Anthropic, no progress feed, expected by +N h"), for Codex cloud (step 3 = "no poll; waiting for PR"), and for an email lane (steps 3-5 collapse into "email artifact arrived 06:30, graded by `_evaluate` at 06:34: PASS").

## 3) Effectiveness

- **Definition of done per registry entry**: `expects: {artifact: pr|email|api_result|file, within: <duration>, schema: <optional JSON schema for structured bodies>, review: required|optional|none}`. A run is `delivered` only when the artifact landed, `schema_ok`, and (if `review: required`) the Anthropic verdict is recorded. "Green run status does not mean the task succeeded" (`R:runtimes-aggregators §3` on Routines) is exactly why the artifact, not the vendor's status, is the unit of done.
- **Evidence**: PR URL + head SHA + CI status; email `Message-ID` + body hash; Jules session id + activity log; Routine run id; the `pr-review` job's own JSONL. Every artifact row links to the local review job so the chain vendor-run → artifact → review → merge is auditable (FINRA-style logging template, `R:crosscut-finance-trading-ai §6` regulatory notes).
- **Review / grading**: `pr-review` = the existing `code-review` skill compiled as today (`agents.py:57-109`) inside a read-only workspace job on the PR head; its verdict is written to `artifacts.merge_gate_verdict` — closing the "in-session verdict never stored" gap (`M:§2.5`). Research artifacts (email/memo) are graded by `_evaluate` with `EVAL_PASS/FAIL` markers (`main.py:949-985`), unchanged.
- **Cross-vendor review asymmetry** (C5): the vendor that produced an artifact never issues its LGTM; Anthropic always does. Cross-vendor *dissent* is additive: an `adversarial-review` registry entry sends the committed memo to Codex cloud (or a second Claude Routine) and the collector files a `DISSENT/CONCUR` artifact next to the Anthropic verdict. Pairwise overlap between reviewer lanes is computed monthly (Jaccard on normalised findings, `R:runtimes-aggregators §3(g)`); a pair >0.7 is flagged "not a second opinion".
- **Provider scoreboard** (`/api/hub/scoreboard`, also fed into `review-and-improve`): per vendor × task class — on-time rate, artifact rate, schema-ok rate, LGTM rate, owner approve/reject counts, follow-up count, quota burn per delivered artifact. `retrospective.skill_performance` (`retrospective.py:39-96`, zero callers today) gets a `lane` group-by and a caller.
- **Qualification ladder** (plan §6g, reused): `shadow` (vendor run fires, artifact ingested, review recorded, nothing merged/trusted) → `canary` (capped share of low-stakes entries) → `qualified` → auto-`demoted` on LGTM-rate or on-time-rate drop. State in `provider_qualifications.yml`; changes via proposals; owner-approved while a lane is young.

### 3.1 Scoreboard metric definitions (per lane × task class, 30-day window)

| Metric | Definition | Source |
|---|---|---|
| on_time_rate | delivered runs with `observed_finished_at ≤ expected_at + expects.within` ÷ expected runs | `vendor_runs` |
| artifact_rate | runs with ≥1 artifact ÷ observed runs | `artifacts` |
| schema_ok_rate | artifacts with `schema_ok` ÷ artifacts with a schema | `artifacts` |
| lgtm_rate | `merge_gate_verdict = lgtm` on first review ÷ reviewed artifacts | `artifacts` |
| rework_count | follow-ups per delivered artifact | child `vendor_runs` |
| owner_accept_rate | `owner_action = approved` ÷ artifacts shown | `artifacts` |
| quota_per_delivery | Δ `used_pct` (or tokens/cost for metered) between fire and delivery ÷ delivered | `quota_snapshots`, `jobs.cost_usd_est` |
| independence_overlap | Jaccard of normalised findings between two reviewer lanes on the same artifact | review job outputs |

Qualification thresholds (initial, tunable by proposal): `canary → qualified` needs ≥20 delivered runs, on_time ≥0.9, lgtm_rate ≥ the local skill's baseline LGTM rate (today 49/60 post-reviews, `M:§2.5`), owner_accept ≥0.8; `qualified → demoted` on any 7-day window with on_time <0.7 or lgtm_rate <0.5, or two `missing` in a row (breaker).

## 4) Scheduling across vendors

- **Single declared intent**: `vendor-schedules.yml` (tracked, validated by a new lint check) is the registry of every vendor-side or server-fired schedule:
  ```yaml
  - key: atlas-thesis-adversarial-codex
    vendor: openai-codex-cloud          # lane
    managed_by: server                  # server fires it (executor: codex-cloud) | vendor (cron lives on vendor side)
    cadence: "0 14 * * 2"               # for adherence only when managed_by: vendor
    trigger: {kind: github-pr, repo: Piserchia/atlas, label: needs-adversarial-review}
    data_class: owner-private           # never `thesis` on a lane without an OK data row
    expects: {artifact: pr, within: 3h, review: required}
    visibility: api | github | email | vendor-app-only
    budget_weight: 2                    # share of the Claude weekly window when vendor == anthropic-routine
  ```
- **Server-managed entries** become `schedules` rows with `executor != local` via the seed script; the existing scheduler loop (`main.py:1327-1362`) enqueues the fire job on cron exactly like a local job (one job per due row, same misfire semantics — fixing commit-before-RPUSH while there).
- **Vendor-managed entries** exist only as expectations: the registry materialises `vendor_runs.expected` rows one cadence ahead; the adherence checker (extension of `schedule_adherence.py`, run by the existing launchd 07:15 timer *and* by the collector loop) flips them to `late`/`missing` and DMs. The owner creates/edits those crons in the vendor app (Routines via `/schedule` need an interactive claude.ai login — `R:crosscut-subscription-automation-tos §3.1`; ChatGPT tasks in the app; Grok at grok.com/tasks) and the registry is the server's copy of that intent. Drift = a finding, not silently absorbed.
- **Cross-vendor de-confliction**: Claude Routines and local Claude jobs share one Max window (`R:claude-anthropic §3` "Routines and cloud sessions draw from the same allowance and add a daily routine-run cap"). The quota poller's Anthropic snapshot gates fan-out: local semaphore stays at prod 2; Routine fires are deferred when `seven_day.used_pct > 70`. Codex fires gate on `primary.usedPercent`; Jules on the daily count (15 free / 100 Pro / 300 Ultra, `R:gemini-google §3`). Starting fan-out per vendor: Claude 2 local + Routines serial, Codex 2, Jules 1-3, per `R:crosscut-subscription-automation-tos §3.10b`.
- **Granularity limits stated**: Routines ≥1 h; Jules scheduled tasks and ChatGPT RRULE support finer intervals; Grok daily/weekdays/weekly/custom; Gemini Scheduled Actions daily/weekly/monthly with stale pre-computed data (`R:gemini-google §2`). Anything needing minute cadence stays local.
- **Kill switches**: `VENDOR_HUB_ENABLED=false` disables all collectors and fire jobs (the `ROUTER_PROVIDERS_ENABLED=anthropic` idea from plan §2 generalised); per-vendor `paused` flag in the registry; a `hub:breaker:<vendor>` Redis key trips after N consecutive `failed` or `missing` runs and DMs (reuses the breaker pattern of `events.py:463-512`, C26).

### 4.1 Initial registry (what moves, what stays) — H1 through H4

| Registry key | Today | Proposed lane | managed_by | data_class | expects |
|---|---|---|---|---|---|
| `atlas-thesis-adversarial` | none (post-review is Anthropic flag-only, `review.py:250`) | Codex cloud `@codex` on a `needs-adversarial-review` PR; Routine second-read | server (GitHub-event trigger on the thesis commit) | owner-private (after §11.8) | pr comment artifact, 3 h, review: n/a (it *is* a review; Anthropic validator stays authoritative) |
| `atlas-build` (Tue/Fri, opus-4-8 workspace) | local | **stays local** (needs atlas `.env`, dispatch MCP, subagents; capability filter) | — | — | — |
| `alpha-scout`, `alpha-governor`, all `atlas-*-evaluate`, swing/trader/value loops | local | **stay local** (credentials, DB, governors, INV-22) | — | — | — |
| `research-report` (`/task research …`) | local sonnet workspace | Claude Routine on a `research` repo branch (repo-scoped, no local files) with local fallback | server (`/fire`) | public | pr/file, 2 h, review: optional (`_evaluate`) |
| `daily-market-brief` | `atlas-daily-brief` local (3/29 failures) | ChatGPT Scheduled Task 06:00 → email | vendor | public | email, 90 min, review: `_evaluate` |
| `x-sentiment-weekly` | none | Grok Automation Fri 15:00 → email → `sentiment_snapshots` | vendor | public | email, 2 h, schema: `{bull, bear, n_posts, handles[]}` |
| `pickem-post-week-followups` | manual | Jules scheduled task (Mon 09:00) on `pickem` repo | vendor | public | pr, 4 h, review: required |
| `bingo-dependency-bump` | none | Jules monthly | vendor | public | pr, 6 h, review: required |
| `content-forge-eval-suite-refresh` | none | Claude Routine monthly (repo-scoped) | vendor cron | public | pr, 6 h, review: required |
| `ai-server-*` (server-patch, new-skill, deploys) | local | **stay local forever** (INV-4/INV-21 pin) | — | — | — |
| `review-and-improve` | local opus-4-7/max idle trigger (most expensive recurring job, `M:§2.5`) | stays local but consumes the scoreboard; SQL pre-pass as `no_llm` script | — | — | — |

Net: 32 of 41 seeded rows are Atlas loops that stay local; the vendor hub takes over research/brief/sentiment/project-chore classes and *adds* adversarial review that does not exist today.

## 5) Project delivery path

1. **Ask** (Telegram `/task`, web, or a registry cron) → policy picks a `code-project` lane → `jules-create` / `codex-cloud-exec` / `routine-fire` job posts the task against the project's canonical GitHub repo (atlas = `Piserchia/atlas` master per `CLAUDE.md`; other projects per `delivery.branch`).
2. **Vendor agent works in its own VM** and opens a PR (Jules `AUTO_CREATE_PR`; Codex cloud PR; Routine instructed to push a branch and open a PR).
3. **Collector** (`POST /api/hooks/github` `pull_request.opened|synchronize`, fallback `gh pr list` poll every 5 min) creates the artifact and enqueues **`pr-review`** (local Anthropic, workspace clone of the PR head, read-only, `code-review` subagent). Verdict stored; owner DM with `Approve merge` / `Reject` / `Ask follow-up`.
4. **Merge**: on the execution lane (INV-4, owner decision 2026-07-31) a non-protected-path LGTM may auto-merge via a guarded-writer `pr-merge` job (`gh pr merge --squash`); protected paths and the ai-server repo always wait for the owner button. Follow-ups reuse the same vendor session (`jules` session id, Routine `/fire` with text) so context is not lost.
5. **Deploy**: unchanged gated path — `atlas-redeploy` / `server-deploy` / `deploy-director` (`M:§2.6` Delivery). The deploy job's result links back to the artifact so the board shows ask → PR → verdict → merge → deploy → healthcheck as one line.
6. **Non-owner-facing outputs** (pickem pages, project sites): never generated on a subscription lane at request time (`R:crosscut-subscription-automation-tos §3.9`); vendor agents produce *code* that the project serves, which is the permitted shape.

## 6) Trading research automation within INV-22

What runs where — nothing changes on the order path: the only order path remains `atlas/swing/swing/executor.py --submit` behind `risk.validate` (`M:§2.6`; `MISSION.md:190-204`). Vendor-native agents never see `projects/atlas/.env`, the atlas DB, Alpaca/Tradier tokens or `/tmp/intents.json`; they only see what is committed to GitHub and what is in a public-data prompt.

| Stage | Where | Vendor adds | Data boundary |
|---|---|---|---|
| Data ingestion, paper supervision, kernel ops, governors | local Claude (unchanged loops) | — | credentials-bearing; stays on the box |
| Weekly thesis composition | local Claude | — | thesis text is committed to the atlas repo as today |
| **Adversarial review of committed memos** | Codex cloud `@codex` on a review PR (GPT-6, high independence) + a Claude Routine second read; Grok Automation optional | independent miss set; DISSENT/CONCUR artifacts | memo content only; Codex plan "Improve the model" toggle verified off (`R:chatgpt-openai §3` data handling); never to Jules or an unpaid Gemini key |
| **Sentiment feature column** | Grok Automation (SuperGrok, email egress) *or* xAI API `x_search` if metered spend is ever approved | only programmatic live-X feed (`R:grok-xai §6`) | prompt = handle list + window; result parsed into an append-only `sentiment_snapshots` table, overlay tag only, forward-paper only (`M:§2.6` Opportunities) |
| **Daily market/earnings brief** | ChatGPT Scheduled Task (email) → Gemini Scheduled Action (app-only, owner reads) | cheap owner briefing | public data only; stored as `email` artifact for the owner, never fed to a signal |
| **Filings / transcripts pulls** | local Claude + `sec-edgar-mcp`/Alpaca MCP (existing); Perplexity `finance_search` only if the owner approves a small metered key | only vendor-native finance tool (`R:crosscut-finance-trading-ai §1`) | metered; owner decision |
| Evaluation / grading (`_evaluate`, governors) | local Claude, pinned | — | unchanged; separated duties (analyst ≠ validator ≠ governor) |

AUP posture: every vendor's clause is an advice/reliance clause satisfied by owner-only paper research with a human on the order path (`R:crosscut-finance-trading-ai §6`); outputs are labelled research, never advice; xAI's securities clause is respected by using Grok only as a sentiment feed. The 2026 evidence that LLM traders mis-size and lose (`R:crosscut-finance-trading-ai §5, §8`) is the reason this design adds *reviewers and features*, not decision-makers. Blocking plumbing the vendor hub does not fix and that should land first: `TRADIER_SANDBOX_TOKEN`/`FINNHUB_TOKEN` provisioning, `weekly.py:316` crash, Alpaca stale-data fallback (`M:§2.6` pain points).

## 7) Vendor plan

| Vendor / surface | Auth | Cost path | ToS status (research) | Task classes here | Collect via | Visibility |
|---|---|---|---|---|---|---|
| **Anthropic — local Claude Agent SDK** (unchanged) | Max `/login` + `claude setup-token` in launchd env (`R:claude-anthropic §7`) | subscription, $0 marginal | **Yes\*** first-party unmodified binary; policy volatile; never `--bare` (`R:crosscut-subscription-automation-tos §3.7`) | review-gate, _evaluate, code-server, atlas loops, chat | own JSONL/OTEL | full (stream-json) |
| **Anthropic — Claude Routines** (cloud, repo-scoped) | claude.ai login to create; per-routine bearer for `/fire` | draws the same Max usage + daily run cap (`R:crosscut-subscription-automation-tos §3.1`) | **Yes** first-party; research preview; 1 h min; not ZDR; consumer data rules | code-project on atlas/project repos, self second-read, off-box resilience (runs when the Mini is down) | GitHub PR/commits; run id from `/fire`; run history web-only | medium (artifact + web) |
| **Google — Jules** | `JULES_API_KEY` (max 3 keys, no expiry) | Free 15 tasks/day, 3 concurrent; AI Pro $19.99 → 100/day, 15 concurrent (`R:gemini-google §3`) | **Allowed** (API product); data terms *not found* → `public`/code-only | code-project canary on non-sensitive repos, CI-failure auto-fix | API polling (`sessions`/`activities`) + PR | good (API) |
| **OpenAI — Codex cloud tasks / `@codex`** | ChatGPT plan device-code login (`~/.codex/auth.json`) | Plus $20 needed for cloud task delegation (Go lacks it; Free "explore" only, `R:chatgpt-openai §4`) — **owner decision** vs the 08-17 "Codex Free" | **Gray/Yes\*** owner-only outputs; API key "recommended" for CI (`R:chatgpt-openai §3`) | adversarial review (top independence), code-project canary | GitHub PR + `account/rateLimits/read` for quota | good (PR + quota RPC) |
| **OpenAI — ChatGPT Scheduled Tasks** | consumer app | 3 (Free) / 5 (Plus) / 15 (Pro) active; RRULE (`R:chatgpt-openai §2`) | consumer app driven by script = **No**; reading the vendor's own email notification = the vendor's designed egress | research-read briefs, owner digests | IMAP poll of owner mailbox (owner decision) | low (email body only) |
| **xAI — Grok Automations** | consumer seat | SuperGrok $30 (paid tiers only) — optional | **Grey**: first-party feature; AUP "using bots to access" untested; Grok Build subscription-headless *not* used here (`R:grok-xai §3, §7`) | X-sentiment feed, event detection | email egress → IMAP | low (email) |
| **Google — Gemini Scheduled Actions / Spark** | consumer account | free (Pro $19.99 for within-the-hour) / Spark Ultra-only | app-only; no egress; stale data (`R:gemini-google §2`) | owner personal briefs | none → `vendor-app-only` | none |
| **Perplexity** | API key only | metered (~$0.07-0.10/grounded job; `finance_search` $5/1k) — owner decision | consumer **No**; API **Yes** (`R:perplexity §3`) | filings/transcripts/estimates as a tool | `GET /v1/agent/{id}` background polling | medium |
| **GitHub Copilot cloud Automations / Agentic Workflows** (optional) | GitHub OAuth / PAT | Copilot Pro $10 (credits); Free = Auto model only (`R:github-copilot §2, §4`) | **Allowed** (SDK/CLI for all subscribers) | GitHub-native scheduled repo chores | Actions run logs + PRs | good |
| **Cursor Automations / Cloud Agents API**, **Kiro Web Automations** (optional, not recommended now) | Cursor key / `KIRO_API_KEY` | Pro $20 each | Allowed (sanctioned SDK / CI keys) | cron→PR | REST + SSE / PR | good |
| **Local Ollama** (plan R1, unchanged) | none | $0 | n/a | utility-classify | in-process | best |

Explicitly not used: Grok Build or Antigravity CLI under subscription on the box (opaque pools, Antigravity third-party-tool ban, macOS sandbox no-op — `R:gemini-google §8`, `R:grok-xai §8`); Claude Managed Agents and OpenAI Agents API (API-key only → INV-3/policy; `R:runtimes-aggregators §3`); OpenClaw/Hermes; LiteLLM daemon (4 GiB floor + supply-chain incident, `R:runtimes-aggregators §8`); Alibaba/Xiaomi/Perplexity consumer plans (written bans).

## 8) Migration & rollout

| Phase | Scope | Entry | Exit | Keeps running | Kill switch |
|---|---|---|---|---|---|
| **H0 — ledger foundations** (no behaviour change) | migration 007; capture dropped usage fields at `session.py:1095`; `resolved_provider='anthropic'`; `providers.yml`/`routing-policy.yml`/`vendor-schedules.yml` skeletons + lint check; `artifacts` rows for local summaries/files; `/api/hub/*` read routes; `/fleet` read-only card | owner signs the protected-path PR (guards deny-list names, lint check) | pytest + lint green; board shows local jobs with tokens/cost; `/fleet` renders | everything | n/a |
| **H1 — collectors, shadow mode** | GitHub webhook + `gh` poller; Jules poller; quota pollers (Claude probe session + status-line file, Codex app-server read); OTLP-HTTP receiver route (optional); adherence extension; `deliverable_ready`/`vendor_run_missing` DMs | owner adds `GITHUB_WEBHOOK_SECRET`, `JULES_API_KEY`, Codex device login; creates 1 Routine + 1 Jules scheduled task on a throwaway branch of a non-critical repo | one week of observed runs with zero unexplained `missing`; quota gauges agree with vendor apps within ±5 pts | everything | `VENDOR_HUB_ENABLED` |
| **H2 — review gate for external artifacts** | `pr-review` job + `merge_gate_verdict`; deliverables inbox + approve/reject/follow-up (Telegram + web); `pr-merge` guarded-writer skill (protected: new executor skill → owner approval) | H1 exit | every external PR of the week has a recorded verdict before merge; no PR merged without one (lint + test) | local review unchanged | per-vendor `paused` |
| **H3 — server-fired lanes** | `ScriptExecutor` (`no_llm`); `routine-fire`, `jules-create`, `codex-cloud-exec` skills; `schedules.executor`; `/fire`; Routine GitHub-event triggers for the adversarial-review flow | owner decision on ChatGPT Plus; routine bearer tokens minted | canary: atlas research memo adversarial-review artifact delivered end-to-end 3 weeks running; qualification ladder `canary` for `code-project` on pickem/bingo | atlas loops unchanged | breaker per vendor |
| **H4 — email-egress lanes** (owner-gated) | IMAP collector with label filter; ChatGPT scheduled brief + Grok sentiment automation registry entries; `sentiment_snapshots` append-only | owner grants mailbox read (see §11) | briefs and sentiment rows appear daily; sentiment used only as overlay tag | — | collector flag |
| **H5 — tune & report** | scoreboard in `review-and-improve`; monthly cost/quota report DM; qualification promotions via proposals; static Fleet board behind CF Access replaces the inline dashboard page | H3/H4 stable | first monthly report with real numbers; `default-model`/lane proposals flowing | — | — |

**Test gates per phase.** H0: migration up/down; `tests/test_hub_registry.py` (registry parse, lint refuses `thesis` on non-OK lanes, one executor per key); contract tests still 8 × 72 skills with `VALID_MODELS` now sourced from `providers.yml`. H1: collector unit tests on recorded fixtures (a GitHub webhook payload, a Jules session JSON, a Codex `RateLimitSnapshot`, a Claude status-line JSON); adherence pure-function tests extended (`schedule_adherence.py` style); a fake-collector conformance test that every collector emits the common event shape. H2: `pr-merge` refuses without `lgtm` (test); `merge_gate_verdict` stamped on a fixture PR; INV-13 600-s timeout now stamps `review_outcome=error` instead of skipping (closes the `main.py:620-626` gap). H3: `ScriptExecutor` runs without spawning the Claude CLI (assert no `claude` subprocess); fire scripts mocked; scheduler enqueues `executor != local` rows. H4: IMAP parser fixtures for ChatGPT and Grok mails; sender map fail-closed. H5: scoreboard SQL tests; `lint_docs.py` registry/docs sync. Every phase: pytest + `python scripts/lint_docs.py` green, CHANGELOG entries, the deploy skill's gate.

Rollback at any phase = flip the switch; vendor-side crons keep running harmlessly (their artifacts just stop being ingested) — the owner is told exactly which vendor crons to pause by hand.

## 9) What gets deleted / rewritten vs kept

**Kept (load-bearing, `M:§6`)**: JSONL audit + summary files; marker protocol; workspace clone + ff-sync; guard predicates and hook wiring; fail-closed skill resolution / tighten-only isolation / deploy-authority gate; SKILL.md as contract; `enqueue_job` + `jobs:queue` + slot-before-BLPOP; out-of-band alerters and the edge Worker; in-session `code-review` gate; Atlas order path + tripwires; SDK/mcp pins.

**Rewritten**: `telegram_bot._MODEL_ALIASES` as allowlist → `providers.yml` registry feeding `VALID_MODELS`, the web dropdown and `_build_options` (`M:§6` "Accidental"); `_job_to_chat` in-process dict → persisted `tasks.origin_*` binding; inline-HTML dashboard → static Fleet board (the old page kept until H5); three Telegram senders → `src/notify.py` used by bot, scripts and hub; ghost commands fixed; `no_llm` dead flag → real `ScriptExecutor`; `schedule_adherence.py` → adherence over both local and vendor runs; `retrospective.skill_performance` gets a caller and a `lane` dimension; dropped `ResultMessage` fields captured; `seed-schedules.sh` gains `executor`/`registry_key`.

**Deliberately NOT built under this lens**: an `Executor` protocol with Codex/Gemini/Grok CLI adapters on the box; per-vendor guard adapters/OS sandboxes; a LiteLLM or OTEL-collector daemon; per-provider BLPOP lists. The accidental complexities the map lists that this design leaves alone (banner regex, payload-as-control-plane, JobKind enum, per-run venv bootstrap, two-repo skill copy drift) are real but orthogonal; they are listed so nobody mistakes "not touched" for "not debt".

**Honest accounting of what this lens does *not* deliver**: no failover for local Anthropic jobs when the Max window is exhausted (Routines share the window; the design only *defers* fires); no vendor progress bars (artifact-level only); no cross-vendor execution of credential-bearing loops; Gemini's scheduled surface is invisible; email lanes are parse-fragile and depend on an owner mailbox grant.

## 10) Risks & mitigations

| Risk | Mitigation |
|---|---|
| Routines are research preview; `/fire` beta header and `/schedule` semantics can change; Claude Code churn is 10 releases/10 days (`R:claude-anthropic §7`) | pin, weekly smoke test of `/fire` + one `claude -p 'ping'`; registry entry falls back to `managed_by: vendor` cron if `/fire` breaks |
| No run-status API for Routines; "green ≠ done" | artifact-as-done; `expects.within` + `missing` alarms; web deep link |
| Claude Routines drain the same Max window as local jobs; daily run cap unpublished | quota probe gating; `budget_weight`; Routines only for repo-scoped work that would otherwise burn local quota anyway |
| Codex plan auth is Gray/Yes\*; goal mode burns windows; auth refresh only "during use" (8-day idle lapse) | owner-only outputs; `features.goals=false`; `otel.metrics_exporter="none"`; daily `codex login status` canary; `account/rateLimits/read` as auth canary (`R:chatgpt-openai §3, §7`) |
| Jules data-handling terms not found | code-only, public repos or non-sensitive branches; never memos/theses |
| Email parsing fragility; mailbox credential on the box; MISSION non-goal "no email … from owner accounts" | read-only IMAP with a label filter and an app password scoped to one label; parsed body stored as artifact only; owner decision recorded; sending is never implemented |
| New inbound route (`/api/hooks/github`) on a tunnel-exposed host | HMAC verification, replay window, rate limit; `gh` polling as the fallback so the route can be disabled |
| Duplicate execution (local schedule and vendor cron both alive) | lint: a registry key may map to exactly one executor; migration checklist per entry |
| Vendor-produced PR merged without review (INV-13 gap becomes a merge gap) | `pr-merge` refuses without `merge_gate_verdict = lgtm` (test) and protected paths always need the owner button |
| Training toggles drift (Claude "Help improve", ChatGPT "Improve the model", Grok seat toggle) turning 30-day into years-long retention (`R:crosscut-benchmarks-reviews §7`) | quarterly owner checklist card; `data_class: thesis` entries refused until the checklist is stamped |
| Owner-side setup burden (routines must be created interactively) | H1 starts with one routine + one Jules task; the registry doubles as the owner's checklist |
| Memory pressure on the 16 GB box | this lens adds *no* resident daemon; OTLP receiver is a FastAPI route; collectors are asyncio tasks |

## 11) Owner decisions required

1. **ChatGPT tier**: move from "Codex Free (probing)" (plan §10.2) to **Plus $20** to unlock Codex cloud task delegation and 5 scheduled tasks — or keep Free and drop the Codex cloud lane (then adversarial review = Claude Routine second-read only).
2. **Mailbox read access** for ChatGPT/Grok task egress (auth config = protected path #2; MISSION non-goal wording covers *sending* — clarify that read-only ingestion is in scope). If declined, those lanes become `vendor-app-only`.
3. **Google**: stay on Jules Free (15/day) or add AI Pro $19.99 (100/day, Scheduled Actions within the hour). Note the Gemini CLI/Antigravity subscription-headless lanes are *not* proposed regardless.
4. **xAI**: SuperGrok $30 for Automations (email sentiment) — yes/no. (Metered `x_search` API remains declined under the 08-17 no-metered rule unless re-opened.)
5. **Perplexity API** small metered key for `finance_search` (~$5-10/mo) — yes/no.
6. **Protected-path PR bundle**: `.env` keys (`JULES_API_KEY`, `GITHUB_WEBHOOK_SECRET`, `ROUTINE_FIRE_TOKEN_*`, IMAP), `guards.py` deny-list names, `lint_docs.py` new check, the new `pr-merge` executor skill.
7. **Which repos vendor agents may touch**: proposed atlas (non-live paths), pickem, bingo, content-forge; **never** ai-server.
8. **Data class policy**: may committed theses go to Claude Routines (30-day retention, no ZDR) and Codex cloud (toggle off), or public-data prompts only?
9. **Confirm training toggles are off** on the Max, ChatGPT and Grok accounts; confirm the Max tier (5x/20x) so the quota gauge scale is right.
10. **GitHub identity for merges**: a fine-grained PAT or GitHub App for `pr-merge` and webhook registration.
11. **Optional lanes**: Copilot Pro / Cursor / Kiro — default *no*.
12. **Backup**: add `vendor_runs`/`artifacts` to `backup.sh` (and, independently urgent, the missing off-site backup, `M:§2.8`).

## 12) Effort & cost

**Effort** (agent time with the existing execution lane; owner time in parentheses): H0 1.5 wk (0.5 d for the protected PR); H1 2 wk (1 d: keys, one Routine, one Jules task, Codex device login); H2 1.5 wk (0.5 d); H3 1.5 wk (0.5 d: tokens, tier decision); H4 1 wk (0.5 d: mailbox grant, vendor task creation); H5 1 wk (0.5 d). **≈ 8-9 agent-weeks + ~4 owner-days**, sequential; H1/H2 can overlap. Smaller than an on-box multi-executor because no containment layer, no JSONL-dialect adapters and no new daemons are built.

**Effort by component (agent-days)**: migration 007 + usage capture 4; `providers.yml`/policy/registry + lint 4; `src/collectors/` (github, jules, quota, adherence) 8; imap 3; otlp route 1; `ScriptExecutor` + three fire skills 4; `pr-review`/`pr-merge` skills + verdict storage 4; Telegram commands/cards + `notify.py` consolidation 5; Fleet board static app + hub API 6; scoreboard + retrospective wiring 3; docs/registries/CHANGELOG/tests throughout 6 → ≈ 48 agent-days.

**Monthly cost** (incremental over today's Max seat): baseline **$0** (Claude Routines on the existing Max, Jules Free, Codex Free without cloud tasks, unpaid Gemini key for utility only); recommended **+$20** (ChatGPT Plus); optional +$19.99 (AI Pro), +$30 (SuperGrok), +$5-10 (Perplexity API), +$10 (Copilot Pro) → **$20-90/mo** depending on §11. Reference point the owner should keep in view: the whole scheduled load metered on Sonnet 5/Opus 5.5 would be ≈ $8-14/mo (`R:crosscut-finance-trading-ai §3`), so every added seat is paid for by *interactive* value or by outputs the subscription lane may not otherwise produce, not by the batch load.

## Appendix A — Coupling points touched (cross-reference to the state map)

| State-map coupling point | Change under this design | Phase |
|---|---|---|
| `session.py:1095` reads only `usage`; drops `num_turns/total_cost_usd/duration_api_ms/model_usage/stop_reason` (`M:§4`) | capture all into `jobs.*` columns and `job_completed` | H0 |
| `telegram_bot.py:122-134` `_MODEL_ALIASES` = CI allowlist via `tests/test_skill_contracts.py:24` | `providers.yml` becomes the source; aliases and web dropdown (`web.py:689-691`) derived | H0 |
| `models.py:97-105` no provider/tokens/cost columns | migration 007 | H0 |
| `main.py:1419-1486` four supervised tasks | + `collector_loop` (fifth); `/health` gains `hub_collectors_ok` | H1 |
| `web.py:49-63` single shared token; dashboard vhost not CF-Access gated (Caddyfile:36-38) | Fleet vhost behind CF Access; hub write routes require token + Access | H1/H5 |
| `schedule_adherence.py` pure report over local schedules | extended to `vendor_runs.expected` | H1 |
| `main.py:1327-1362` scheduler inserts local Job rows only | honours `schedules.executor`; commit-before-RPUSH fix | H3 |
| `skills.py:55` `no_llm` dead | `ScriptExecutor` for fire/poll jobs | H3 |
| `review.py:247-256` fixed reviewer, verdict flag-only; `main.py:620-626` timeout skips without verdict | `pr-review` records `merge_gate_verdict`; timeout stamps `error` | H2 |
| `telegram_bot.py:38,1028` `_job_to_chat` in-process | `tasks.origin_channel/origin_ref` persisted | H2 |
| `retrospective.py:39-96` `skill_performance` zero callers | scoreboard caller with `lane` group-by | H5 |
| `guards.py:148-149,261-262` deny only `ANTHROPIC_API_KEY` | add `JULES_API_KEY`, `ROUTINE_FIRE_TOKEN_*`, `GITHUB_WEBHOOK_SECRET`, IMAP names (protected path) | H0 (owner PR) |
| `scripts/seed-schedules.sh:22-47` sole payload writer | gains `executor`/`registry_key`; registry lint cross-checks | H3 |
| `events.py:463-512` breaker keyed on skill failures | `hub:breaker:<vendor>` sibling keyed on vendor `failed/missing` | H3 |

Untouched on purpose: `session.py:650-816` (`_build_options`), `guards.py` hook transport, `workspaces.py`, `mcp_dispatch.py`/`mcp_projects.py`, `quota.py` global pause (vendor deferral is a *separate* gate; the single Anthropic pause stays correct because the box still runs one vendor).
