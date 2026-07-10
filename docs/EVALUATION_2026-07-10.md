# ai-server: Evaluation 2026-07-10 — runtime audit, cleanup & subagent-suite plan

> **Audience**: Chris (owner) and future Claude sessions.
> **Date**: 2026-07-10
> **Scope**: the whole repo, the live runtime on the Mac Mini, the jobs database,
> the audit logs, the skill ("subagent") suite, and a dedicated deep-dive into
> `projects/atlas` (run as a parallel agent session; findings in § 5).
> **Method**: evidence-based. Every finding cites a file, a SQL query result,
> a log line, or a launchctl entry. Where the April evaluation
> ([`EVALUATION_2026-04-18.md`](EVALUATION_2026-04-18.md)) measured the
> *architecture* against an ideal, this one measures the *runtime behavior*
> against what the architecture promises.
> **Companion**: the executable remediation plan lives at
> [`docs/superpowers/plans/2026-07-10-eval-remediation.md`](superpowers/plans/2026-07-10-eval-remediation.md).

---

## Implementation status (live)

Update this table as remediation tasks land (same convention as the April doc).
Task IDs reference the remediation plan.

| Task | Priority | Title | Status | Commit | Date |
|------|----------|-------|--------|--------|------|
| T1 | P0 | Unstrand the 2 phantom `queued` jobs | PROPOSED | — | — |
| T2 | P0 | Fix backups (launchd PATH) + untrack committed tarball | PROPOSED | — | — |
| T3 | P0 | Finish R2 + heartbeat-worker human setup steps | PROPOSED | — | — |
| T4 | P1 | Fix stale-Job bug: post-review + escalation never fire | PROPOSED | — | — |
| T5 | P1 | Fix `review.py` SDK API + review-the-whole-session diff | PROPOSED | — | — |
| T6 | P1 | Startup reconciliation for stranded `queued` jobs | PROPOSED | — | — |
| T7 | P1 | Router rules for the atlas skill family + trigger-contract test | PROPOSED | — | — |
| T8 | P1 | Model tier map; retire hardcoded `claude-opus-4-7` pins | PROPOSED | — | — |
| T9 | P1 | Silence INFO log spam (bot 25 MB, runner SDK lines) | PROPOSED | — | — |
| T10 | P1 | Loop-liveness checks in `server-upkeep` | PROPOSED | — | — |
| T11 | P2 | Atlas web app: enqueue by `kind`, not description prefix | PROPOSED | — | — |
| T12 | P2 | Repo & docs cleanup batch (see § 4 table) | PROPOSED | — | — |
| T13 | P2 | Decide + seed missing schedules (research / ideas) | PROPOSED | — | — |
| T14 | P2 | Run eval harness baseline; add atlas + self-diagnose cases | PROPOSED | — | — |
| T15 | P2 | Decide plugin exposure for SDK job sessions | PROPOSED | — | — |
| T16 | P3 | Atlas project remediation items (§ 5) | PROPOSED | — | — |
| T17 | P3 | Backlog: bingo audit, quality-signal automation, sudo decision | PROPOSED | — | — |

---

## 1. Executive verdict

**The architecture is sound and the skill bodies are well-written. The failure
is in the plumbing between them.** Four defects — none visible to the 560-test
suite or the doc linter, both of which pass clean — mean several of the
system's most important feedback loops have **never actually executed**:

1. The code-review sub-agent has fired **zero times** since Phase 4 shipped
   (no `code_review_started` event exists in any of 273 audit-log files;
   `review_outcome` is NULL on all 192 jobs). Cause: a stale-ORM-instance bug
   (§ 3.3) plus a nonexistent SDK method in `review.py` (§ 3.4). INV-13
   ("server-patch always requires a passing code-review") is currently
   unenforceable.
2. Frontmatter escalation (`on_failure` model promotion) is unreachable for
   the same stale-instance reason — failures skip straight to self-diagnose.
3. `review-and-improve` — the self-improvement loop, MISSION objective H —
   has run **zero times in 3 months**. Two phantom rows stuck in `queued`
   (present in Postgres, absent from Redis) make the idle-queue trigger
   permanently see a busy queue (§ 3.5). Downstream, the proposals table is
   empty and the eval harness has never produced a result.
4. Nightly backups have failed with `pg_dump: command not found` **since
   April** (launchd PATH; `com.assistant.backup` last exit status 127). The
   only backup that exists is `backup-2026-04-17.tar.gz` — which is also,
   incorrectly, committed to git. 43 `server-upkeep` runs stayed silent
   because its checklist verifies *off-site* backup freshness only, never
   local (§ 3.7).

Separately, the newest and most-used skill family (atlas) is mostly **not
running through its skills at all**: the atlas web app enqueues
`atlas-chat` / `atlas-report` / `atlas-scout` work as `kind=task` with a
description prefix, the router has no rules for them, so they execute as
generic Sonnet sessions without their skill body, turn caps, or escalation
config (§ 3.6). They limp along only because the sessions read the SKILL.md
off disk mid-run.

**The meta-lesson** (this is the "how could we improve the system" answer in
one sentence): *every autonomous loop needs an external liveness check,
because a broken loop cannot report its own brokenness.* The system already
learned this once for the runner itself (the heartbeat worker); it now needs
the same pattern for its feedback loops — review coverage, retrospective
recency, backup freshness — wired into `server-upkeep` (T10).

**What is genuinely working well** (verified, not assumed):

- All 3 server processes + Caddy + cloudflared + Postgres + Redis up;
  local and **public** `/health` return full OK JSON.
- The write-back loop works (12 `_writeback` jobs, CHANGELOG hygiene held).
- The learning loop works (17 `_learning_apply` jobs; module knowledge files
  grew from 1 file/~30 lines in April to 16 files/543 lines today, and the
  `learn(...)` commits show real, specific gotchas).
- `self-diagnose` output quality is high — a sampled run correctly identified
  a synthetic test sentinel, ran the three documented verification checks,
  and declined to act. The skills are good; the dispatch layer is what fails.
- Doc lint (8 checks) and 560 tests pass in 2s. Structural doc integrity held.
- Atlas hosting itself is live: 3 launchd services running, port 8791 proxied,
  Cloudflare Access in front.

---

## 2. What is running on the Mac right now

Verified via `launchctl list`, `ps`, port probes, and log inspection
(2026-07-10 ~18:00 EDT).

| launchd label | What | State | Notes |
|---|---|---|---|
| `com.assistant.runner` | job loop (4 async tasks) | running (since 16:37) | err log spammed by SDK INFO lines (T9) |
| `com.assistant.web` | FastAPI :8080 | running | `/health` OK locally and via `health.chrispiserchia.com` |
| `com.assistant.bot` | Telegram poller | running | `bot.err.log` = **25 MB of httpx INFO** incl. bot token in URLs (T9) |
| `com.assistant.caddy` | reverse proxy :80 | running | apex + dashboard + atlas + bingo + health vhosts |
| `com.assistant.backup` | nightly 04:00 | **failing, exit 127** | `pg_dump: command not found` every night since April (T2) |
| `com.assistant.healthcheck-all` | 5-min probe | running (exit 0) | |
| `com.assistant.project.atlas` | Next.js :8791 | running | |
| `com.assistant.project.atlas-dash-scheduler` | Python vertical | running | |
| `com.assistant.project.atlas-pm-edge` | Python vertical | running | |
| `com.assistant.project.baseball-bingo` | FastAPI :8790 | running | |
| `homebrew.mxcl.postgresql@15` | Postgres (`assistant` + `atlas` DBs) | running | |
| `homebrew.mxcl.redis` | Redis :6379 | running | queue depth 0 |
| `homebrew.mxcl.ollama` | Ollama 0.18.3 :11434 | running | **not used by this system** (Anthropic-only per MISSION); owner's own |
| cloudflared (pid 392) | named tunnel | running since Mon | |

Retired-but-lingering: `market-tracker` launchd plists are gone (good), but
`volumes/logs/project.market-tracker*.log` remain (~500 KB, last write
2026-07-09) — archive candidates (T12).

**Job/DB reality** (`assistant` DB): 192 jobs since 2026-04-17. 2 rows stuck
`queued` with an **empty Redis queue** — `server-upkeep` from 2026-07-09 23:00
EDT and `atlas-daily-brief` from 2026-07-10 12:55 EDT (i.e., last night's
upkeep and today's daily brief silently never ran). 3 schedules exist
(upkeep daily, atlas daily brief, atlas weekly sweep); `seed-schedules.sh`
only ever seeds upkeep — the MISSION-B/E research and idea schedules don't
exist anywhere (T13).

---

## 3. Subagent-suite evaluation

"Subagents" in this system = 24 skills (dispatched as SDK sessions by the
runner) + 2 in-process sub-agents (`review.py` code reviewer, `learning.py`
Haiku classifier) + the event-trigger rules engine.

### 3.1 Usage, from the jobs table (192 jobs, 2026-04-17 → 07-10)

| resolved_skill | completed | failed | notes |
|---|---|---|---|
| **(none — generic task)** | **74** | 5 | 39% of all jobs ran with no skill at all — see § 3.6 |
| server-upkeep | 43 | — | workhorse; but see § 3.7 for what it doesn't check |
| _learning_apply | 17 | — | learning loop alive ✓ |
| self-diagnose | 16 | — | mostly event/escalation-spawned; output quality high |
| _writeback | 12 | — | write-back loop alive ✓ |
| atlas-portfolio | 4 | — | correctly enqueued by kind ✓ |
| god | 3 | — | April: built bingo Phase 2 + telegram redesign |
| app-patch | 3 | — | all April; `review_outcome` NULL on all (§ 3.3) |
| chat | 2 | 2 | |
| research-report / research-deep / atlas-report-sweep | 1 each | 1 | |
| **review-and-improve** | **0** | — | **never ran** (§ 3.5) |
| **code-review** (standalone or sub-agent) | **0** | — | **never ran** (§ 3.3–3.4) |
| new-project, new-skill, project-evaluate, restore, project-update-poll, idea-generation, atlas-chat/report/scout/daily-brief/redeploy (as skills) | 0 | — | atlas ones run daily — as skill-less generic tasks |

Signals: `user_rating` set on 2/192 jobs (rate buttons exist in the Telegram
thread UI; they're just rarely pressed). `review_outcome` 0/192. `proposals`
table empty. 30 child jobs (escalations/writebacks/learnings) — the child-job
machinery works.

### 3.2 The correctness question ("are the subagents even being used correctly?")

Mostly **no**, for four concrete, fixable reasons — detailed in 3.3–3.6.
When a skill *is* reached correctly (server-upkeep, self-diagnose,
atlas-portfolio, the internal pair), behavior matches its SKILL.md and
quality is good.

### 3.3 Defect A — post-review and escalation read a stale Job instance (T4)

`_process_job` loads the Job **once, while it is still `queued`**
(`src/runner/main.py:182-186`). `run_session` later stamps
`resolved_skill/model/effort` **into the DB via a separate session**
(`src/runner/session.py:516-524`) — the detached in-memory instance never
sees it. Consequences:

- `_maybe_review` (`main.py:292`): `skill_name = job.resolved_skill` → `None`
  → returns immediately. **Post-review has never run for any job**, including
  the 3 April `app-patch` jobs whose frontmatter says `post_review.trigger:
  always`. Zero `code_review_started` events exist across all audit logs.
- `_maybe_escalate` (`main.py:425-428`): same stale `None` → "no skill = can't
  escalate via config" → jumps to level-2 self-diagnose. **Every skill's
  `escalation.on_failure` frontmatter is dead config.**

Fix shape: re-fetch the Job row (or use `result["skill"]`, which
`run_session` already returns) before both hooks. Exact code in plan T4.

### 3.4 Defect B — `review.py` would crash even if reached (T5)

- `review.py:181` iterates `client.process_message(prompt)` — **not a
  ClaudeSDKClient method**. The working pattern is
  `async with client: await client.query(...); async for m in
  client.receive_response()` (as `session.py` does). Had Defect A not masked
  it, every review would raise `AttributeError`, be caught, and stamp
  `changes_requested` blindly.
- `get_git_diff(cwd, ref="HEAD~1")` (`review.py:120`) reviews only the last
  commit. `app-patch`/`server-patch` sessions routinely make several commits —
  most of the session's work would escape review. Fix: capture pre-session
  `HEAD` and diff against it (plan T5).
- Model is hardcoded `claude-opus-4-7` (`review.py:170`) — see § 3.9.

### 3.5 Defect C — stranded `queued` jobs block the entire self-improvement loop (T1, T6)

Startup reconciliation (INV-15, `reconcile.py`) covers jobs stranded in
`running` — but not jobs whose Redis queue entry was consumed (or lost)
while the DB row stayed `queued`. Two such rows exist right now (§ 2).
Because `_check_idle_queue_review` (`events.py:253-281`) counts
`queued + running` rows, the queue **never looks idle**, so the
review-and-improve trigger — the only thing that runs it, per
`seed-schedules.sh` — never fires. This single mechanism explains:
0 review-and-improve runs, 0 proposals, 0 eval-harness runs, and no
consumer for the `context_consumption` / `stale_context_warnings` /
`context_budget_report` retrospective machinery built in April (Recs 2, 7, 8
— shipped, then starved).

Fix: T1 unblocks today by SQL; T6 extends `reconcile.py` to reconcile
DB-`queued` vs Redis at startup so it can't recur.

### 3.6 Defect D — the atlas skill family is bypassed at enqueue time (T7, T11)

Today's job list (all `kind=task`, `resolved_skill=NULL`):
`atlas-report: asset CRDO`, `atlas-chat: asset HYPE`, `atlas-scout: run stock
scout`, `atlas-report: portfolio brief`, … The router
(`src/runner/router.py`) has exactly one atlas rule (`redeploy atlas`);
nothing matches `atlas-chat|report|scout`, and the trigger phrases the SKILL
descriptions advertise (“`/task scout stocks`”, “`/task daily brief`”) have
**no corresponding rule** — the descriptions are contracts nobody implements.
`docs/TROUBLESHOOTING.md` already documents the rule ("skill jobs must
enqueue by kind, not description prefix"), and `atlas-portfolio` +
the two schedules were fixed accordingly — but the atlas web app's
chat/report/scout enqueue path was not.

Effect of running skill-less: default Sonnet with the **full default tool
set** (incl. Write/Edit the skills deliberately withhold), no `max_turns`
cap, no escalation, server-root cwd (so sessions burn turns re-orienting and
trip `_writeback` noise in the server repo), and the skill body only takes
effect because the session notices and reads it mid-run — visible in the
audit INDEX keywords (`"atlas-chat", "skill", "read"`).

Fix: router safety-net rules server-side (T7) **and** the atlas app enqueues
by `kind` (T11) **and** a contract test so a skill description can never
again advertise a trigger the router doesn't implement (T7).

### 3.7 Defect E — backups dead since April; upkeep couldn't see it (T2, T3, T10)

`scripts/backup.sh` line 17 fails nightly: launchd's default PATH lacks
`/opt/homebrew/...`, so `pg_dump` isn't found (exit 127, visible in
`launchctl list` and 6 KB of identical `backup.err.log` lines). The only
backup ever made is April 17's — tracked in git, which is itself wrong
(volumes are runtime state). `server-upkeep` step 8b checks **off-site (R2)**
freshness and treats "offsite-not-configured" as fine — there is no local
backup freshness check at all, so 43 runs stayed silent. The `restore` skill
currently has nothing meaningful to restore. Additionally the two human setup
steps from PR #1 (rclone/R2 remote; heartbeat-worker deploy) appear
incomplete — though the public `/health` route the worker needs is live.

### 3.8 Skill quality (the prompts themselves): good, occasionally excellent

Read in full: `atlas-report` (exemplary — deterministic CLI contract, payload
schema, failure modes, single-writer exemption, dated gotchas),
`server-upkeep` (crisp procedure + SILENT protocol + its own discovered
gotchas), `god`, `chat`, `code-review`, `_writeback`, `_learning_apply`.
Sampled outputs (self-diagnose summary, learn commits) show the instructions
are actually followed. **The "refactor ineffective documentation" concern
lands on the dispatch/registry layer, not on skill bodies.** Two body-level
nits: `god` and `self-diagnose` reference `docs/Troubleshooting.md`
(wrong case — works only because APFS is case-insensitive), and
`code-review`'s registry row claims a standalone+sub-agent role it has never
performed.

### 3.9 Model pins are one generation stale (T8)

`claude-opus-4-7` is pinned in 10 skill frontmatters (incl. every atlas
`escalation.on_failure`), `review.py:170`, the Telegram alias map
(`telegram_bot.py:118`), the web dropdown (`web.py:479`), and
`session._MODEL_BUDGETS`. Opus 4.8 (`claude-opus-4-8`) is current. Version
strings are scattered across ~15 files; each model generation bump is a
15-file sweep. Fix: one tier map in `config.py` (`MODEL_FAST / MODEL_DEFAULT /
MODEL_DEEP`), everything else references tiers; skill frontmatter may keep
explicit pins but the registry documents the tier convention (T8).

### 3.10 Plugins load into every SDK job session (T15)

`.claude/settings.json` (project-scoped, which `setting_sources=["project"]`
pulls into every job session) enables 6 plugins including superpowers.
Evidence it's active inside jobs: **17 job sessions used the `Skill` tool**,
and the April god-jobs built the Telegram redesign through superpowers
plans/worktrees (productive!). Cost: every job — including a 12-turn
atlas-chat answer — carries the plugin hook preamble that *mandates* skill
invocation and brainstorming-before-acting. This is a real, currently
implicit, tokens-and-behavior tradeoff. Decision options in plan T15
(recommendation: keep plugins for heavyweight builder skills, exclude for the
light high-frequency ones via a per-skill `setting_sources` frontmatter field).

### 3.11 Capability gaps (ranked)

1. **No loop-liveness monitoring** — the pattern that would have caught
   Defects A/C/E within a day. Add to `server-upkeep`: last
   review-and-improve completion < 7d; `review_outcome` non-NULL on recent
   post_review skills; newest local backup < 26h; any `com.assistant.*`
   launchd job with non-zero last exit status (T10).
2. **No trigger-contract enforcement** — skills can declare triggers that
   don't exist (§ 3.6). A pure-function test closes this permanently (T7).
3. **Eval harness never run** — 3 cases (chat, code-review, research-report),
   `evals/results/` empty. No case covers the atlas family, the highest-volume
   work. Baseline + 2 cases + wiring verification (T14).
4. **Quality signal starvation** — 2 ratings in 3 months; `review_outcome`
   never populated (fixable via T4/T5); atlas already computes deterministic
   evaluator scores per report that never reach the jobs table. Backlog:
   harvest structured quality signals instead of hoping for manual ratings (T17).
5. **Scheduled research/ideas absent** — MISSION objectives B and E have no
   schedule rows; either seed them or descope the MISSION text (T13; decision).
6. **self-diagnose can't touch sudo-level infra** (tunnel config, plists
   needing admin) — April feedback memory explicitly asked for this. Needs a
   deliberate decision (NOPASSWD scoped helper vs. keep human-in-loop) (T17).
7. **god is undocumented in MISSION §M** — it legitimately bypasses every
   ceiling (by design, human-invoked). One paragraph in MISSION §M makes the
   exception explicit instead of implicit (T12).

---

## 4. Repo & documentation hygiene

Doc lint passes; the issues below are the ones an existence-checker can't see.
(Execution: plan T2/T12.)

### 4.1 Delete / untrack (dead weight)

| Path | Evidence | Action |
|---|---|---|
| `.handoff/` (16 tracked files incl. a .patch) | Self-declares "ARCHIVED … historical reference only"; Rec-10 shipped 2026-04-18 | `git rm -r`; history preserves it |
| `volumes/backups/backup-2026-04-17.tar.gz` | Runtime artifact tracked in git | `git rm --cached`; ignore `volumes/` wholesale |
| `.worktrees/telegram-thread-interface` + branch `feature/telegram-thread-interface` | Plan doc says ✅ COMPLETE, shipped 2026-07-09 | verify merged (`git log main..feature/telegram-thread-interface`), then `git worktree remove` + delete branch |
| `volumes/jobs.db` (0 bytes) | No writer anywhere in `src/`, `scripts/`, `evals/`; recently gitignored | delete; if it reappears, the creator is an SDK session — find via audit logs |
| `volumes/logs/project.market-tracker*.log` | project retired 2026-07-09 | archive or delete |
| `.DS_Store` (root, projects/) | Finder noise | add to `.gitignore` |

### 4.2 Fix in place (drift / broken formatting)

| Doc | Problem | Fix |
|---|---|---|
| `.context/SKILLS_REGISTRY.md` | Blank line splits the Installed table after `new-project` — renders as two tables | remove blank line |
| `SERVER.md` + `router.py` docstring | Reference a "Haiku-based `route` skill" fallback that was never built | fix prose: rule-router only, generic fallback (YAGNI — don't build it) |
| Troubleshooting casing | File is `docs/TROUBLESHOOTING.md`; `CLAUDE.md`'s doc map, `INDEX.md`, `god` + `self-diagnose` `context_files` say `Troubleshooting.md` (works only on case-insensitive APFS) | standardize on the actual filename everywhere (`grep -rn "Troubleshooting.md"`) |
| `.context/PROJECTS_REGISTRY.md` | `research` row (Phase 2) — `projects/research/` doesn't exist on disk; the skill bootstraps it but no schedule ever enqueues it | annotate "not yet bootstrapped — no schedule" or resolve via T13 |
| `docs/README.md` | Table omits `EVALUATION_2026-04-18.md`, `superpowers/` dirs, and this doc | add rows |
| `.env.example` | Missing `POSTGRES_PASSWORD` (present in real `.env`) | add key with placeholder |
| `MISSION.md` | §M omits `god`; phase-table link casing; model names as hard versions | add god paragraph; fix link; state models by tier |
| `GETSTARTED.md` / `TEARDOWN.md` | Untouched since 2026-04-17; TEARDOWN references market-tracker plists that no longer exist; GETSTARTED predates 4-task runner + reconcile | refresh pass |
| `.context/SYSTEM.md` | "Active workstreams" grows monotonically (now 7 bullets of shipped history) | compress shipped phases to one line; keep the section for *active* work only |
| `.claude/settings.local.json` | 90+ one-shot permission entries accreted since April (`kill 7196`, one-off `cp`s) | prune to durable patterns |

### 4.3 Keep (called out so nobody "cleans" them)

Phase plans 3–6 (historical record, explicitly valuable), `docs/assistant-system-design.md`
(superseded-where-disagrees banner is already in docs/README), `EVALUATION_2026-04-18.md`
(status table is live), `.context/PROTOCOL.md` (immutable), module skills files
(the learning loop's output), `docs/superpowers/{plans,specs}` (shipped-work records).

---

## 5. Atlas project deep-dive

Full report (produced by a dedicated parallel agent session):
[`EVALUATION_2026-07-10-atlas.md`](EVALUATION_2026-07-10-atlas.md).
Remediation items → plan T16. The short version:

**Operationally strong.** All three launchd services healthy (the `-15` exit
codes are routine `kickstart -k` SIGTERMs, not crashes); plists correct and
secret-free; `curl :8791` → 200; dev and runtime repos in sync at `7f5b9e3`;
21 sequential dbmate migrations, no gaps; deploys gated by real pytest runs.
And the **skill ↔ project contract is fully intact**: all ~25 CLI verbs,
flags, paths, and endpoints the 7 atlas skills invoke were verified to exist
in `atlas_dash/cli.py` and scripts — zero hard mismatches. The dispatch
problem in § 3.6 is entirely on the server/web-enqueue side, not the
project's CLI surface.

**The gaps, ranked:**

1. **Fails the server documentation standard**: no `.context/CONTEXT.md`
   (the 5-section format) and no `.context/CHANGELOG.md` in either repo —
   the flagship project is the one that skips the standard. (A root
   `CHANGELOG.md` is genuinely maintained but 4 commits behind and in the
   wrong place.) The server registry also still says "Three dedicated
   skills" — there are seven.
2. **CLAUDE.md asserts a wrong security model**: "reached only over
   Tailscale / Tailnet-only" — the live perimeter is Cloudflare Access. The
   go-live amendment was explicitly promised in `AI_SERVER_INTEGRATION.md`
   and never made. Also claims "Anthropic API" where reality is
   subscription-auth via server skills.
3. **Learn-loop vs pull-only clone tension** (open atlas BACKLOG item):
   `atlas-dash learn` writes *tracked* files inside the runtime clone —
   `experts_knowledge/crypto_analyst.md` is dirty right now — and any
   dev-side touch of the same file turns the next ff-only deploy into a
   refusal. Structural fix: move `experts_knowledge/` out of git (packet
   already passes absolute paths).
4. **pm-edge `rates_implied` pipeline is dark** and spams the err log every
   tick (`no ZQ quotes from yfinance`); 1 of 3 pipelines effectively off.
5. **Manifest drift**: `env_required` lists `ANTHROPIC_API_KEY`
   (contradicts the subscription-only policy), `git.repo` says "pending"
   when the GitHub remote exists.
6. Hygiene: tracked `.DS_Store`, missing `*.egg-info/` ignore, stale
   one-time runbooks needing historical banners, 536-line SESSION_HANDOFF
   needing rotation, a leftover `backup-2026-07-09` branch and
   `.superpowers/sdd/` scratch in the runtime clone (human-confirm deletes),
   no Python lockfile, and a server-side broken pointer in
   `skills/atlas-redeploy/GOTCHAS.md` to an atlas troubleshooting doc that
   doesn't exist.

---

## 6. Priorities

- **P0 (today, human or god session)**: T1 (two SQL statements), T2 (one PATH
  line + kickstart + untrack), T3 (the two documented human setup steps).
  Everything in § 3.5/3.7 stays broken until these land.
- **P1 (one gated server-patch PR)**: T4–T10. T4+T6 are the highest-leverage
  code changes in the system right now: they resurrect code review,
  escalation, and the entire self-improvement loop. T7 makes the largest
  skill family actually run as skills.
- **P2 (normal cadence)**: T11 (atlas repo, direct-push per app-patch policy),
  T12 (docs batch), T13–T15 (decisions + baseline).
- **P3 (backlog)**: T16 atlas items, T17 (bingo audit per April memory,
  quality-signal harvesting, sudo decision).

## 7. Explicitly not doing

- No retrieval/RAG layer (April Rec 14 stays deferred — corpus still small).
- No new skills until dispatch is fixed — April's warning ("easier to add a
  17th skill than make the 16th better") applied; there are now 24.
- No multi-runner concurrency work, no framework generalization, no
  cross-provider anything (MISSION non-goals).
- No `.context/PROTOCOL.md` changes.

---

*Method note: produced by a Claude Fable 5 session (max effort) with a
parallel sub-agent for the atlas audit — read-only except documentation,
memory, and this report. Queries and log excerpts are reproducible; see
`volumes/audit_log/INDEX.jsonl`, `launchctl list`, and the SQL in § 3.1.*
