# Changelog: runner

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-08-05 — post-review resurrected (0/516 → live) + escalation refetch

**Files changed**: `src/runner/main.py`, `src/runner/review.py`,
`tests/test_review.py`, `scripts/seed-schedules.sh`.

Found by the closed-loop arc's own code review (three rounds — the first two
rounds' more ambitious "review gates the deferred deploy child" design was
scoped OUT after review kept finding holes in the deep promotion-ordering
surgery it required; the deploy is already gated by the builder's in-session
`code-review` subagent + `atlas_redeploy`'s pytest gates, so post_review
stays a SECOND belt that flags, exactly like app-patch/server-patch).

1. **post_review had NEVER fired — 0 of 516 jobs** (INV-13's second belt was
   dead since inception): `_maybe_review` read `job.resolved_skill` off the
   ORM instance loaded BEFORE `run_session`, but the session stamps
   `resolved_skill` via a separate DB session — the detached instance never
   sees it, so `skill_name` was always `None` and the review returned early.
   Fix: `_process_job` refetches the Job row right after `_finish_job(
   completed)`; every resolved_skill-keyed post-step (review, writeback
   gate, learning gate) now sees the stamped value. Same refetch on the
   FAILURE path so level-0 `escalation.on_failure` reads the real skill
   (it was silently jumping to self-diagnose for task-kind jobs).
2. **Wrong-diff guard**: reviewing `HEAD~1` is wrong when the workspace's
   `sync_canonical` ff failed (routine on a dirty/diverged dev clone) or the
   session committed nothing — the review would grade someone else's commit.
   `review.head_commit_epoch` + `is_stale_head` (pure, tested): HEAD older
   than `job.started_at - 120s` → skip with audit event
   `post_review_skipped` (reason=stale_head or no_diff).
3. **`post_review.reviewer_model`/`reviewer_effort` were dead keys**
   (reviewer hardcoded opus-4-7 for everyone): `run_code_review` takes
   optional `model`/`effort`, wired from the skill's post_review dict;
   defaults unchanged.
4. **post_review FLAGS, it does not park** (the design the review rounds
   converged on): activating post_review surfaced that the old
   blocker→`awaiting_user` park was buggy dead code — it published a SECOND
   `jobs:done` after the completion DM already fired (owner told "completed"
   on a blocker), stranded task state, and let writeback/learning run on a
   parked diff. And it bought nothing: the review runs AFTER the code is
   committed/pushed, so parking can't un-merge — the real merge gate is each
   skill's IN-SESSION `code-review` subagent before the push. So
   `_maybe_review` now stamps `review_outcome` (job stays `completed`), and
   on blocker/error emits a `post_review_flagged` audit event + a
   `review_flagged` task DM (new additive branch in telegram_bot's
   tasks:notify consumer). Surfaced by `review_outcome` in /status, the
   retrospective, and the weekly manager sweep. No `awaiting_user`, no
   task-advance skip, no double-publish.
5. **Reviewer is FIXED (opus-4-7/high), not skill-chosen**: `run_code_review`
   dropped the `reviewer_model`/`reviewer_effort` passthrough — a skill must
   not be able to downgrade the reviewer that grades its own diffs.
   atlas-build's frontmatter reviewer keys were removed (they were the only
   caller trying to set them).
6. **`_refetch_job` helper** dedupes the identical post-session refetch used
   by both the success and failure paths (one place to change the refresh
   semantics).
7. **seed-schedules.sh**: every upsert value is a psql bound variable
   (`-v n/c/k/d/p/nx`) inside a quoted heredoc (nothing bash-expands — a
   payload with a quote or `$()` can no longer break seeding); empty
   next-slot → NOW() via `COALESCE(NULLIF(:'nx','')::timestamptz, NOW())`;
   new `job_payload` column carried via `COALESCE(EXCLUDED.job_payload,
   schedules.job_payload)` so out-of-band scoping survives re-seeds.

Deliberately NOT changed (reviewed across four rounds and scoped out):
promotion ordering is untouched — `promote_deferred_for` runs
unconditionally on completion as before; the deploy child is dispatched
immediately by atlas-build (no `depends_on`-on-review); `session.py`,
`plans.py`, `workspaces.py` are unchanged from HEAD (an earlier round's
"review gates the deferred deploy child" machinery — ReviewGate,
blocks_dependents, retained-workspace review, promotion reorder,
fail_taskless_dependents — was fully reverted: it required deep
promotion-ordering surgery that kept generating bugs, and the deploy is
already gated by the in-session review + the executor's test gates).
post_review runs under `_POST_REVIEW_TIMEOUT_SECONDS` (600s) — now that it
actually fires, a hung reviewer sub-agent can't pin a concurrency slot while
/health stays green; a timeout is an audited skip, not a verdict. The
reviewed diff is the canonical checkout's `HEAD~1` (unchanged, pre-existing):
the `is_stale_head` guard rejects an OLDER foreign HEAD but not a NEWER one,
so on the multi-writer atlas canonical a foreign commit landing between the
build's push and the ff-sync can be mis-graded — low harm now that
post_review only FLAGS (a rare mis-stamp the evaluator/owner dismisses),
never gates. Failure-path escalation now reads the real `resolved_skill`, so
a failed atlas-build escalates into a stronger-model REBUILD (its own resume
check completes-transitions-only on already-pushed work, so no duplication)
instead of a read-only self-diagnose — an improvement.

Follow-up backlog: task-less deferred dependents of a terminally-failed job
aren't cascade-failed (pre-existing, unrelated); a task-less job flagged by
post_review has no chat_id so its `review_flagged` DM is dropped — the audit
event + review_outcome still record it, and the weekly atlas-evaluate now
reads `review_outcome` for each build to surface a flag as a backlog item.

**Verify**: `pipenv run pytest tests/test_review.py -q` (25 passed;
TestStaleHeadGuard covers the wrong-diff guard); full suite green; after the
next deploy, `psql assistant -c "SELECT review_outcome, count(*) FROM jobs
WHERE resolved_skill IN ('app-patch','server-patch','atlas-build') GROUP BY
1;"` should start showing non-NULL outcomes (the 0/516 symptom clears).

## 2026-07-31 — MCP tools joined allowed_tools (the second dispatch blocker)

**Files changed**: `src/runner/session.py` — the MCP injection block now
appends the injected servers' tool names (`mcp__dispatch__enqueue_job`,
`mcp__projects__{list_projects,get_project,read_project_logs,restart_project}`)
to `allowed_tools`, mirroring the Task-tool auto-add. Without it, acceptEdits
sessions had MCP servers but no permission to call them — acceptEdits
auto-accepts EDITS only, and a headless session can answer no permission
prompt. Proven live 2026-07-31: the deploy-director's first autonomous
dispatch attempt ran a clean preflight, prepared the executor description,
and was then denied `enqueue_job` twice. This was the SECOND layer of the
dispatch blocker (the first: plan mode blocks MCP outright) — dispatch had
only ever worked under bypassPermissions, which is also why
review-and-improve's dispatch stayed dead even after its plan→acceptEdits
fix. The readonly guard profile (INV-20) still hook-denies restart_project
for read-only skills; hooks fire before permission evaluation.

## 2026-07-31 — Workspace directive aligned to the execution lane

**Files changed**: `src/runner/session.py` — the injected workspace directive
told every server-scoped session "server code lands via PR + deploy ... never
push to main from here", which contradicted the new autonomous execution lane
(WS-C). It now defers to the skill's declared merge flow: lane-authorized
skills (server-patch/new-skill, post-LGTM + owner notification) may push main;
everything else branches + PRs; protected paths always stop at a PR. No
behavior change outside the directive text.

## 2026-07-31 — Read-only guard profile: oversight skills get structural read-only + dispatch

**Why**: `permission_mode: plan` blocks MCP tools (proven live 2026-07-30 —
deploy-director's enqueue_job unreachable; review-and-improve's dispatch
silently dead for weeks), so dispatch-capable oversight skills must run
acceptEdits — which until now left their read-only-ness prose-only.

**guards.py**: new READ-ONLY profile alongside the workspace profile. Pure
predicates `readonly_file_violation` (Write/Edit/MultiEdit/NotebookEdit denied
outright — no path exceptions, temp dirs included) and
`readonly_bash_violation` (mutation denylist: output redirection except
/dev/null + fd-dups, quote-masked so quoted SQL `>` comparisons pass; file
mutators; git mutators with `git fetch` as the sanctioned refs-only exception;
launchctl mutating subcommands, list/print allowed; alembic
upgrade/downgrade/revision/stamp; dbmate; createdb/dropdb; pip/pipenv
install/uninstall/sync/lock; npm/npx/brew; redis-cli
set/del/push/pop/flush/expire; psql write verbs — statement-start anchored, so
identifiers like `project-update-poll`/`created_at` never false-positive;
sudo/kill/crontab/keychain/API-key hard denials).
`make_readonly_guard_hooks(job_id)` → 3 PreToolUse matchers: file tools, Bash,
and `.*restart_project` (suffix re-checked in-hook); `enqueue_job`
deliberately unmatched. Denials audited `guard_denied` with
`profile: "read-only"`. The guarantee, honestly: file tools structurally
denied; Bash is a best-effort denylist, not a sandbox (SDK Seatbelt stays the
SYSTEM.md-tracked OS-level closure).

**session.py**: `_build_options` attaches the readonly profile whenever
`skill_cfg.privilege_class == "read-only"` — every isolation tier and
permission mode (belt under plan, load-bearing under acceptEdits); read-only
wins over workspace hooks if both somehow apply. Workspace wiring untouched.

**lint**: oversight roles ⇒ read-only + mode ∈ {plan, acceptEdits}; new
role-independent rule: needs-dispatch-mcp + read-only ⇒ acceptEdits.

**Skills**: system-manager + 4 division managers plan→acceptEdits +
needs-dispatch-mcp + dispatch-authority paragraphs; review-and-improve
plan→acceptEdits + privilege_class read-only (matches its charter row) +
gotcha recording the silent-dispatch weeks; deploy-director gotcha updated —
its read-only contract is now hook-enforced, not prose-only.

Tests: tests/test_guards.py +127 (69-entry deny matrix, 37-entry allow matrix
of real oversight command vocabulary, 8 hook-contract); tests/test_doc_lint.py
+6 (rule logic on synthetic trees).


## 2026-07-31 — Event-loop circuit breaker + global (task-less) deferred promotion

**1. Circuit breaker in `src/runner/events.py`** (2026-07-30 incident: ~17
self-diagnose jobs event-spawned into a substrate where self-diagnose itself
was broken — `'Server' object has no attribute 'list_tools'` — each failure
feeding the 2-in-10-min window; only per-target dedup bounded it):
- Pure `should_trip_breaker(recent_failures, threshold=5)`: groups failed
  jobs by normalized error signature (`_error_signature`: whitespace-collapsed
  first 80 chars; None/blank -> "unknown"); any cluster >= threshold returns
  that signature (largest cluster wins, ties lexicographic).
- `_check_circuit_breaker()` runs FIRST each cycle: if `KEY_EVENTS_BREAKER`
  exists -> skip all event-trigger spawning (skill-failure, project-health,
  correlated) but NOT the idle-queue review; one info line per cycle at most.
  On trip: `SET NX EX TTL_EVENTS_BREAKER` (30 min), one error-level log, and
  EXACTLY ONE `self-diagnose` job ("CIRCUIT BREAKER tripped: N failed jobs ...
  share the error signature '<sig>'", `target_kind: circuit-breaker`,
  `created_by: event-trigger:circuit-breaker`) — its completion summary DMs
  the owner via the normal path. The check crashes fail OPEN in the loop's
  non-fatal try/except style; new constants `BREAKER_WINDOW_MINUTES = 10`,
  `BREAKER_FAILURE_THRESHOLD = 5`, `BREAKER_SIGNATURE_LEN = 80`.

**2. Global deferred promotion in `src/runner/plans.py`**: `promote_deferred_for`
early-returned for task-less completing jobs, stranding any task-less
`depends_on` child forever (the limitation deploy-director's SKILL.md works
around). Task-scoped sibling promotion is behaviorally unchanged; the function
now ALSO scans `status='deferred' AND task_id IS NULL` rows (bounded:
`TASKLESS_PROMOTION_SCAN_LIMIT = 200`, oldest first), Python-filters for
`payload.depends_on` naming the completed job (pure `names_dependency`), and
applies the identical flow: `deps_satisfied` over a completed-set covering all
of each candidate's deps, INV-9-guarded deferred->queued UPDATE, RPUSH,
`job_promoted` audit, per-item isolation, never raises. escalation_map is
passed EMPTY on this path — escalation lineage is derived from a task's own
job set and has no task-less equivalent — so a dep satisfied only via a
completed escalation retry does not promote a task-less child (conservative:
under-promotes, never wrongly promotes). NOTE: `main.py` gated the call on
`job.task_id` — that gate was lifted in the integration commit immediately
after this merge, so promotion now fires for every completing job.

Tests: `tests/test_events.py` +23 (signature normalization, breaker boundary/
mixed/empty/None cases, loop gating incl. fail-open), `tests/test_plans.py`
+10 (`names_dependency`, task-less `deps_satisfied` semantics). Full suite
898 passed; lint_docs all-PASS.


## 2026-07-30 — Enqueue visibility race fix (stranded queued jobs) + epoch heartbeat with TTL

**BUG 1 — `_process_job` dropped popped ids whose row wasn't visible yet.**
BLPOP can return a job id before the INSERTing transaction's commit is visible
to the runner's SELECT: `_tick_schedules` RPUSHes *inside* an open transaction
(add → flush → rpush → … commit on scope exit), and even commit-then-RPUSH
producers race the BLPOP by sub-ms. The old code logged "job not found" and
returned — the Redis entry was consumed, the row stayed `status='queued'`
forever. Bit tonight: job e38d0028 ("job not found" at its exact created_at
second; re-pushed by hand).

**Fix (consumer-side, covers every producer)** in `src/runner/main.py`:
- `_process_job` retries the SELECT over ~2s (`_JOB_FETCH_DELAYS` =
  (0.0, 0.2, 0.3, 0.5, 1.0); fresh session per attempt — only a new
  transaction sees a commit that landed after the previous attempt began).
- Still missing → `note_missing_job(id, _requeued_missing_ids)` (deterministic,
  no-I/O helper + module-level set): first miss → RPUSH the id back to the
  queue **TAIL** exactly once; a repeat miss → error-log and drop for good, so
  a truly-deleted row can't ping-pong. The set stays bounded (cleared on found
  and on drop). The requeue RPUSH is guarded per the loop's 2026-07-28 Redis
  try/except hygiene — a Redis blip logs the id instead of raising.
- Found-but-not-queued rows return silently as before (cancel race etc.).

Tests: `tests/test_job_visibility.py` (8 — decision sequences + retry-schedule
contract).

**BUG 2a — heartbeat hardened for off-runner consumers**: `_job_loop` now
writes `KEY_RUNNER_HEARTBEAT` as **epoch seconds** with a **15-min TTL**
(`TTL_RUNNER_HEARTBEAT`, new constant in `src/db.py` beside the key name —
db.py comment updated in the same commit). Epoch so
`scripts/healthcheck-all.sh` can age-check it from bash; TTL so a dead
runner's key disappears instead of sitting stale-but-parsable. Companions:
gateway `/health` parses epoch with ISO fallback (see gateway CHANGELOG);
`scripts/healthcheck-all.sh` gained an independent runner-down Telegram DM
(heartbeat missing/>600s AND no launchd PID for com.assistant.runner; creds
READ from the checkout's .env; one DM per 30 min via a volumes/ state file;
fully guarded so project probes can never be blocked). Closes the liveness
blind spot from the 2026-07-30 incident (runner down ~a day —
docs/TROUBLESHOOTING.md "runner down, launchctl shows no PID with last
exit 0").

## 2026-07-30 — mcp 2.0.0 regression: pin `mcp<2` (dispatch/projects MCP injection broken)

**Incident** (same evening as the runner-down fix, surfaced by the hierarchy's
first pass): every `needs-dispatch-mcp` / `needs-projects-mcp` session failed
with `'Server' object has no attribute 'list_tools'` (review-and-improve + the
two event-triggered self-diagnose jobs — the event triggers' first-ever real
firings, ironically). Cause: claude-agent-sdk 0.1.x pins `mcp>=1.19.0`
with no upper bound; a routine `pipenv lock` on 2026-07-30 pulled mcp 2.0.0,
which removed the 1.x lowlevel `Server.list_tools` API the SDK's
`create_sdk_mcp_server` bridge calls. Last working dispatch-MCP job: 2026-07-28 22:46 (pre-re-lock).

**Fix**: explicit `"mcp<2"` in pyproject dependencies (drop only with the
deliberate SDK 0.2.x migration); both venvs repaired in place with
`pip install "mcp<2"` (mcp 1.28.1) pending the next deploy's re-lock.
Bonus finding: mcp 2.0 in the venv silently suppressed 40 MCP-dependent tests
from collection — the suite is back to full strength (842).

## 2026-07-30 — Runner-down incident: stdlib/structlog logging mismatch + supervisor exit code

**Incident**: prod runner found down (launchctl: no PID, last exit 0) with the
queue stranded. Root-cause chain: `events.py` logs with structlog-style kwargs
on a stdlib `logging.getLogger` logger → `TypeError: Logger._log() got an
unexpected keyword argument 'poll_interval'` the moment `event_loop` starts →
the 2026-07-28 subsystem supervisor correctly shuts the process down — but
`main()` exits **0**, and launchd's `KeepAlive {SuccessfulExit: false}` never
restarts successful exits, so the runner stayed down. Latent since Phase 4
(42ef735): before supervision, the event_loop task died silently at startup,
which also means event triggers had never actually run in production.

**Changes**:
- `events.py` (×4), `retention.py` (×1), `review.py` (×1): structlog-style
  kwargs → %-style stdlib logging. The last two instances (a multiline call in
  events.py and review.py's `code review complete` — INV-13's own machinery)
  were found by the new lint check, not by grep: AST beats regex here.
- `main.main` now returns an exit code (`sys.exit(asyncio.run(main()))`):
  crash path exits 1 so launchd actually restarts a crashed runner — the
  supervision fix's stated intent, previously unreachable.
- Regression test `tests/test_events.py::TestEventLoopStartup` (a pre-set
  shutdown event exercises exactly the startup log line, no DB).
- Lint check 13 `check_logger_style` (scripts/lint_docs.py, AST-based): bans
  structlog-style kwargs on stdlib loggers across src/ — the whole bug class,
  which pure-function tests can't catch because the crash is at log time in
  paths tests never execute.

**Why**: a repo mixing structlog (main, quota) and stdlib logging (everything
else) will keep regrowing this bug unless it's linted structurally.

Closed a cluster of silent-failure paths the 2026-07-28 audit found where a
documented invariant wasn't actually enforced:

- **`main._cancel_listener`** (INV-8): per-iteration try/except + UUID
  validation. A malformed cancel payload (`uuid.UUID("garbage")`) or a
  transient Redis error previously killed the listener permanently while
  `/health` stayed green (only `_job_loop` heartbeats).
- **`main._finish_job`** (INV-9): guards `WHERE status != 'cancelled'` +
  rowcount check, so the cancel-race (cancel lands, then a trailing
  `_finish_job(completed)` resurrects the job) can't overwrite a user cancel.
  `completed→awaiting_user` (review blocker) is still allowed.
- **`main._job_loop`** (M5): `is_paused` + `blpop` are now inside the Redis
  try/except — a Redis blip no longer kills the loop and strands the runner.
- **`main.main`** (M5): supervises the 4 async tasks — if any exits on its own
  (dead scheduler/cancel-listener), it shuts the process down so launchd
  restarts a clean one instead of limping invisibly. (Code-review fix: cancel
  survivors ONLY on the crash path — on graceful SIGTERM `_job_loop` is draining
  in-flight jobs, so cancelling it there would abort running sessions.)
- **`review.run_code_review` + `main._maybe_review`** (INV-13): the review gate
  fails CLOSED. A review that can't run now returns `ReviewOutcome.error` →
  `awaiting_user`, instead of `changes_requested` (which doesn't gate) letting
  an unreviewed diff ship.
- **`plans.promote_deferred_for` / `fail_dependents_of`** (T4): per-item
  isolation — one failed subtask promotion/cascade no longer aborts the loop
  and strands ready siblings.
- **`workspaces._run_git`** (M3): catches `TimeoutExpired` → returncode 124, so
  a hung `git pull --ff-only` in `sync_canonical`'s finally can't turn an
  already-pushed, successful job into a failure that re-runs done work.
- **`config.server_root`** default corrected (`assistant` → `ai-server`) — the
  wrong default silently repointed every volume path when SERVER_ROOT was unset.
- **`audit_log.py`** docstring: `job_completed` writes `usage`+`duration_seconds`,
  not the previously-documented `cost_usd` (none — subscription auth).

Behavioral tests for these land with the fakeredis/DB harness (Batch 4).

## 2026-07-28 — Segregation code-review fixes (Phases A–E)

Addressed the code-review sub-agent's should-fixes (all were latent — they bite
the first dev-repo project, not today's legacy ones):
- **main.py `_maybe_review` / `_verify_writeback`** now resolve the diff cwd via
  `session._resolve_cwd(job, resolved_skill)` (delivery-aware) instead of always
  the runtime clone — otherwise a dev-repo project (which commits to the dev
  repo) would show an empty diff and SILENTLY SKIP the code-review gate.
- **main.py `DeployNeedsApproval`** now fails terminally with an actionable nudge
  instead of parking in `awaiting_user` — there is no deploy-resume path (the
  telegram Approve button completes a task, it does not re-enqueue a deploy), so
  parking would hang forever.
- **`skills/project-redeploy`** fails CLOSED when a project has no
  `delivery.deploy` block or (service/api) empty `services` — a bare pull with no
  restart ships stale code. Fixed the slug example (slug is the projects/ dir
  name, may differ from subdomain — `baseball-bingo` not `bingo`).
- **router.py** `\bredeploy\b.*\batlas\b` → atlas-redeploy so "redeploy the atlas
  dashboard" keeps atlas's bespoke pipeline instead of the generic engine.
- Doc nits: corrected the `_resolve_delivery` docstring (described a runtime
  special-case that never existed) and noted the INV-2 pre-execution-rejection
  exception in SYSTEM.md.

## 2026-07-27 — Generic project-redeploy router rule (segregation Phase C)

**Files changed**: `src/runner/router.py` — added `\bredeploy\b` → `project-redeploy`
AFTER the atlas + server-deploy rules (first-match-wins, so "redeploy atlas" →
atlas-redeploy and "deploy the server" → server-deploy still win; "redeploy
bingo" → the generic engine). "deploy X" phrasings the regex misses fall to the
LLM router via the new skill's description.

**Why**: `skills/project-redeploy/SKILL.md` (new) is the contract-driven deploy
engine that reads a project's `delivery.deploy` block; it needs a routing entry.
`atlas-redeploy` is kept (hard rule: never delete a skill) and remains atlas's
path until atlas's manifest carries an explicit delivery block (Phase E).

## 2026-07-27 — Project delivery enforcement (segregation Phase B)

**Files created**: `src/runner/delivery.py` (contract enforcement: dev-repo
cwd scoping + deploy-authority gate; pure decision fns + fail-open manifest
loader), `tests/test_delivery.py` (24).

**Files changed**:
- `src/runner/session.py` — `_resolve_project(job, skill_name)` resolves the
  session cwd from the project's delivery contract: `topology: dev-repo` scopes
  a NON-deploy session to the canonical dev repo (the separate git thread),
  audited as `project_cwd_resolved`. run_session runs the deploy-authority gate
  BEFORE any work (raises `DeployRefused`/`DeployNeedsApproval`).
- `src/runner/main.py` — `_process_job` catches `DeployRefused` (terminal fail,
  NO escalation — a policy refusal must not retry) and `DeployNeedsApproval`
  (→ awaiting_user + notify).
- `src/runner/guards.py` — git write subcommands (commit/add/rebase/merge added
  to reset/checkout/clean/restore) now count as mutators, so a workspace-tier
  session that reaches into a runtime clone via absolute path
  (`cd <runtime-clone> && git add -A && git commit`) is guard-denied. The
  runtime clone lives under server_root (already a protected root), so no new
  plumbing. Guards bind workspace-tier only → content projects (isolation:none)
  that legitimately commit are unaffected.

**Why**: make the single-writer / deployability rules structural instead of
prose. Combined with dev-repo cwd scoping, the EXISTING workspace guard (denies
writes outside the per-job clone) already prevents a dev-repo patch session from
touching the runtime clone — the git-mutator addition is belt-and-suspenders for
explicit-absolute-path reaches. See
`docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`.

**Side effects**: NONE until a project opts in with a `delivery` block —
legacy/derived manifests resolve to the runtime clone exactly as before. A
deploy job whose project is `deployable:false`/`manual-only` (autonomous) now
fails with a clear contract reason instead of running.

**Gotchas discovered**: the deploy gate raises before `job_started` is logged
(like preflight failures already do) — the `deploy_authority` audit event is the
record. Adding `git add`/`commit` to the mutator set is safe ONLY because it is
gated on a protected-root reference AND guards bind workspace-tier sessions only.

## 2026-07-27 — SDK-native overhaul: container lane removed, guard hooks + subagents + structured outputs

**Files created**: `src/runner/guards.py` (PreToolUse guard hooks — the
container lane's containment duty, now enforced in-process and binding even
under bypassPermissions), `src/runner/agents.py` (SKILL.md → SDK
AgentDefinition compilation; frontmatter `subagents:` → in-session Task-tool
delegation), `tests/test_guards.py`, `tests/test_agents.py`.

**Files removed**: `src/runner/executors.py`, `tests/test_executors.py`,
`Dockerfile.agent` — the `claude -p`-in-docker lane and its image.

**Files changed**:
- `src/runner/session.py` — single execution path (in-process SDK only);
  wires guard hooks for workspace-tier sessions + `agents=` subagents +
  effort validation (`xhigh` is a native SDK value on 0.1.81 — passed
  through, NOT remapped); typed
  rate-limit handling (`RateLimitEvent` → QuotaExhausted, audited as
  `rate_limit_status`); ResultMessage.is_error now fails the job when no
  usable text was produced (parity with the removed container lane).
- `src/runner/workspaces.py` — `resolve_isolation(skill, payload)` (2-arg);
  tiers are `none | workspace | host`; retired `container` maps to workspace.
- `src/runner/quota.py` — `detect_from_rate_limit(info)`: typed detection
  from RateLimitInfo (status/resets_at); string heuristic kept as fallback.
  Retires the "quota detection is heuristic" debt item.
- `src/runner/review.py` — **bug fix**: the reviewer called the nonexistent
  `ClaudeSDKClient.process_message()`; the blanket except turned EVERY review
  into `changes_requested` silently (no LGTM/blocker verdict was ever real).
  Rewritten on `query()` + `output_format` json_schema (verdict enum enforced
  by the SDK; `outcome_from_structured` pure, text parse kept as fallback).
- `src/runner/llm_router.py` / `src/runner/learning.py` — structured outputs
  via `output_format` (+ `route_from_structured` / `proposal_from_obj` pure
  validators); text parsers kept as fallback; router catalog now reads
  `SkillConfig.description` instead of re-parsing YAML per skill.
- `src/runner/main.py` — startup check no longer shells out to
  `claude --version`; verifies no ANTHROPIC_API_KEY + SDK import + bundled
  (or system) CLI presence.
- `src/config.py` — container settings removed (CONTAINER_RUNTIME,
  AGENT_IMAGE, CONTAINER_MEMORY, CONTAINER_CPUS, CLAUDE_CODE_OAUTH_TOKEN);
  stale env vars are ignored (`extra="ignore"`).
- `evals/run.py` — judge ported from `claude -p` subprocess to an SDK
  `query()` call (last CLI shell-out in the codebase).
- `pyproject.toml` — `claude-agent-sdk>=0.1.63,<0.2` (0.2.x exists; upgrade
  is a deliberate follow-up with its own test pass).

**Why**: the mission is Agent-SDK-native on subscription auth. The docker
lane was our only self-managed CLI execution path, was disabled by default
(empty CONTAINER_RUNTIME), and duplicated the SDK lane's audit plumbing.
The SDK's own surface (hooks, agents, output_format, RateLimitEvent,
bundled CLI) now covers everything the lane did, with enforcement instead
of convention. Full rationale: `docs/SDK_MIGRATION_2026-07-27.md`.

**Side effects**: INV-17 redefined (guard hooks instead of containers);
`isolation: container` frontmatter is lint-flagged (runtime still maps it);
sessions that error with no output now FAIL instead of completing empty.

**Gotchas discovered**: `ClaudeAgentOptions.effort` accepts only
low|medium|high|max — the repo's `xhigh` was passing through unvalidated;
hook input keys are snake_case (`tool_name`, `tool_input`); workspace clones
live UNDER server_root, so guard path scans must mask the workspace path
before matching protected roots.

## 2026-07-12 — Push gates injected into workspace directives

**Files changed**: `src/runner/session.py` — both workspace directive
variants (project + server) now carry the push-gate procedure inline:
verify-before-commit, fetch+rebase-before-push, retry-once-then-report,
never force-push. Needed because isolated project sessions load the
PROJECT's CLAUDE.md (not the server's), so the gates must arrive via the
injected directive. Companion doc changes: CLAUDE.md § Git push gates
(server sessions) and PROJECT_PROTOCOL.md Phase 4 (project sessions).

**Why**: today's incidents were both push-procedure failures (unpushed prod
commit; dev push without pull). Convention → enforced procedure in every
surface a session reads.

## 2026-07-12 — P4: hygiene — silent excepts now log

**Files changed**: `src/runner/session.py` (`_publish_stream` debug-logs,
`publish_done` warn-logs), `src/runner/main.py` (audit-index append failures
debug-logged). No behavior change beyond observability — these paths
previously swallowed every exception with `pass`.

**Why**: a lost done-notification or stream drop was undiagnosable.

## 2026-07-12 — P2/P3: plan DAG orchestration, LLM router fallback, text-marker events, acceptance evaluator

**Files changed**:
- `src/runner/plans.py` (new) — plan validation (`validate_plan`, `topo_order`,
  `deps_satisfied` — all pure), DAG spawn (`spawn_plan_jobs`: roots queued,
  dependents deferred), promotion (`promote_deferred_for` — a completed
  escalation retry satisfies its failed original), failure cascade
  (`fail_dependents_of`), drain check (`plan_jobs_remaining`).
- `src/runner/llm_router.py` (new) — the LLM routing fallback the router
  docstring promised since Phase 4: one-turn Haiku pick from the skill catalog
  (may return `plan`); `parse_route_response` is pure + fail-open to generic.
- `src/runner/session.py` — `_resolve_skill` is async and audits every
  `routing_decision` (method=rule|llm|fallback + confidence);
  `extract_text_events` (pure): TASK_COMPLETE / TASK_QUESTION / EVAL_PASS /
  EVAL_FAIL line markers + `<<<TASK_PLAN` JSON block in a session's final text
  are synthesized into audit events runner-side — executor-agnostic (works in
  containers where the host audit log isn't mounted) and race-free (job id is
  also now injected into every non-chat directive).
- `src/runner/main.py` — task lifecycle rework: `task_plan` → validate → store
  on Task → auto-approve (default) spawns the DAG (`plan`/`plan_approval`
  notifies); plan subtasks never auto-continue (DAG drain detection instead);
  `task_complete` → `_evaluate` acceptance job (auto_evaluate default) instead
  of pending_approval; `_evaluate` outcomes: EVAL_PASS auto-closes with
  evidence (`completed` notify + Reopen), EVAL_FAIL spawns a fix round
  (max_eval_rounds=2) then hands to the user; deferred promotion after each
  completion; terminal escalation cascades failure to dependents; review/
  writeback/learning skip all `_`-prefixed internal kinds.
- `src/runner/mcp_dispatch.py` — `create_server(job)`: dispatched children
  inherit task_id/parent_job_id; `depends_on` arg creates deferred jobs.
- `src/config.py` — `llm_router_enabled`, `plan_auto_approve` (true),
  `auto_evaluate` (true), `max_eval_rounds` (2).
- `skills/plan/SKILL.md` (new), `skills/_evaluate/SKILL.md` (new).
- `tests/test_plans.py` (new, 30 tests: plan validation/topo/deps, marker
  extraction, route parsing, triage).

**Why**: "single Telegram ask → decompose → execute → evaluate" was the
mission's core promise; before this, /task mapped to exactly one skill job
and "done" was self-reported.

**Side effects**: tasks now auto-close on evaluator pass (user overrules via
Reopen button); pending_approval remains for auto_evaluate=false and for
evaluator no-verdict edge cases. New audit events: routing_decision,
plan_stored, evaluator_spawned, eval_fix_spawned, job_promoted.

**Gotchas discovered**: dispatch MCP tools must be built per-session (closure)
— a module-level job context would be shared mutable state across concurrent
sessions.

## 2026-07-12 — P1: per-job workspace isolation + container executor + concurrency 4

**Files changed**:
- `src/runner/workspaces.py` (new) — isolation tiers (`none|workspace|container|host`),
  per-job git clones under `volumes/workspaces/`, canonical ff-sync after push,
  cleanup (failed jobs keep theirs), prune helper for server-upkeep.
- `src/runner/executors.py` (new) — container lane: `claude -p --output-format
  stream-json` via docker CLI, mapped to the SAME audit events as the SDK lane;
  runtime/token availability probe; `docker kill` cancel path; OAuth-token-only
  env (ANTHROPIC_API_KEY actively stripped).
- `src/runner/session.py` — run_session resolves isolation, creates workspaces,
  picks the executor, syncs + cleans up after; `_build_server_directive` gained
  workspace/container variants (`canonical_cwd`, `context_root` params);
  `_build_task_context` event-loop hack REPLACED by async prefetch +
  pure `build_task_context(turns, task_id)` — context-load failures now audit
  as `task_context_load_failed` instead of silently losing the conversation;
  `interrupt()` also kills containers.
- `src/registry/skills.py` — `isolation` frontmatter field (default `none`).
- `src/config.py` — `max_concurrent_jobs` 2→4; container settings
  (`container_runtime`, `agent_image`, `container_memory`, `container_cpus`,
  `claude_code_oauth_token`); `workspaces_dir` property.
- Frontmatter: app-patch + project-evaluate → `isolation: workspace`;
  server-patch → `isolation: container` (dead `needs-projects-mcp` tag removed —
  body never used it); god → `isolation: host` (explicit break-glass lane).
- `Dockerfile.agent` (new), `docs/CONTAINERS.md` (new), `.env.example` —
  container lane setup.
- `tests/test_workspaces.py` (new, 17 tests incl. real-git clone/push/sync/
  collision cases), `tests/test_executors.py` (new, 15 tests for command
  construction + stream-json parity parsing).

**Why**: two concurrent jobs shared checkouts (single-writer incidents
2026-07-09) and every session ran bare on the host. Now: code-writing skills
get throwaway clones (collision-proof, blast-radius-contained), the riskiest
automated skill (server-patch) additionally runs containerized when a runtime
is configured, god remains host-native by explicit decision (phone break-glass),
and concurrency rises to 4.

**Side effects**: audit logs gain `workspace_created` / `workspace_synced` /
`workspace_fallback` / `container_started` / `task_context_load_failed` events.
Failed jobs leave their workspace on disk for debugging (pruned after 7 days).
Container lane passes `--model` but not effort (no stable CLI flag) — documented
in docs/CONTAINERS.md.

**Gotchas discovered**: git refuses pushes to a checked-out branch, so
workspaces re-point origin at the canonical's real remote and the canonical is
ff-synced afterward; when a canonical has no remote, sync fetches from the
workspace instead.

## 2026-07-12 — P0: server-deploy routing rules

**Files changed**:
- `src/runner/router.py` — Added `server-deploy` rules (`deploy the server`,
  `server-deploy`, etc.) ABOVE the server-patch rules so a deploy request is a
  pull+gate+restart, never a code-change session. Part of the P0 dev→prod
  pipeline (new skill `skills/server-deploy/`, new `scripts/sync-learnings.sh`,
  hourly `com.assistant.sync-learnings` launchd timer).

**Why**: Production checkout drift was being hand-"rescued" (commits cbbdd02,
8cfbfc6, 60e1e5c). Deploys and learning sync are now first-class, single-writer
topology documented in CLAUDE.md.

**Side effects**: "update the server to..." still routes to server-patch;
"deploy the server" now routes to server-deploy.

**Gotchas discovered**: The runner cannot restart itself synchronously —
server-deploy uses a detached delayed `launchctl kickstart` (see SKILL.md).
## 2026-07-11 — L2 self-diagnose false positive for cancelled sentinel (5ef4d36d)

**Files changed**:
- `docs/TROUBLESHOOTING.md` — New symptom section
  "self-diagnose fires for a god sentinel job that died with exit code 143
  (SIGTERM)" with diagnostic queries and prevention notes.

**Why**: L2 escalation `5f7d8f62` fired for job `5ef4d36d` with
`Error: unknown`. Root cause traced to two-race compound:
(a) Cancel race — the parallel god session `184b480f` (see entry below)
executed `UPDATE jobs SET status='cancelled'` then killed the sentinel PID.
The sentinel's SIGTERM handler in the runner then wrote `job_failed` and
`UPDATE jobs SET status='failed'`, overwriting the cancel. So the DB row
shows `failed` and the escalation logic couldn't tell it was intentional.
(b) Escalation blindness — the L2 spawn path in `main.py` around
L494-L500 doesn't check whether the failure was a user/system cancellation
(exit 143 from `created_by LIKE 'auto-continue:%'` is a strong signal it was).

**Diagnosis only** (medium-server risk, needs server-patch):
1. In the SIGTERM handler, use `UPDATE ... WHERE status != 'cancelled'` so a
   prior cancel is preserved.
2. In the escalation spawn, suppress self-diagnose when the failed job was
   an auto-continue sentinel and died with exit 143.

**Side effects**: None — this session only appended docs.

_Evidence: jobs `5ef4d36d` (sentinel), `184b480f` (killer god), `5f7d8f62`
(this self-diagnose)._

## 2026-07-11 — Live cleanup: killed rogue auto-continue caught in the act

**Files changed**: None (runtime state only).

**Why**: While investigating "check on my last task" (job `184b480f`), I discovered the exact defect documented in the previous entry firing in real time. Job `0651defb` (the diagnostic session) ended with an A/B/C question to the user but emitted no `task_question` event. The runner's `_update_task_after_job` fell through to auto-continue and enqueued job `5ef4d36d` with description `"Continue to the next phase of the plan."` on task `20daab34` ("why are these changes for these last tasks not deploying"). By the time I looked at its audit log, `5ef4d36d` had already `ls`'d `docs/superpowers/plans/`, read `2026-07-10-eval-remediation.md`, checked PR #3, and was preparing to work on Wave 2 of the eval remediation — **on a task that literally asks "why aren't my changes deploying"**. Perfect reproduction of the hijack in the wild.

**Action taken**: `UPDATE jobs SET status='cancelled'` on `5ef4d36d`; killed PID `94785`; `UPDATE tasks SET status='failed'` on `20daab34`. Documenting this reproduction as additional evidence for the fix work (patch `superpowers:brainstorming` to emit `task_question`; patch `_update_task_after_job` sentinel to carry task context).

**Side effects**: One rogue god session cancelled mid-flight before it could commit unrelated code.

## 2026-07-11 — Diagnosis: task-hijack defect (brainstorming + auto-continue)

**Files changed**:
- `.context/modules/runner/skills/GOTCHAS.md` — Added detailed entry
  "Brainstorming clarifying questions get 'Continue to next phase' hijacked"
  documenting a two-part defect discovered while debugging the 2026-07-11
  baseball-bingo redeploy tasks.

**Why**: Investigation of user question "why are these changes for these last
tasks not deploying" traced back to two combined failures:
(1) `superpowers:brainstorming` asks clarifying questions but never emits a
`task_question` audit event, so the runner never enters `awaiting_user`;
(2) the auto-continue sentinel `"Continue to the next phase of the plan."`
carries no task context, so the next job reads `MEMORY.md` and continues
whatever plan it finds there — silently swapping the user's actual task for
an unrelated one. Evidence: tasks `b59375a8`, `3bfb65aa`; jobs `137c27eb`,
`1681307a`, `2867bcd7`. No code changes made in this session — this is a
diagnosis-only writeup documenting the defect for a follow-up fix.

**Side effects**: None (documentation only).

## 2026-07-11 — T12 cleanup: remove stale "route skill fallback" claim from router.py docstring

**Files changed**:
- `src/runner/router.py` — Removed never-implemented "LLM fallback via route skill" claim from module docstring. Routing has always been rule-based; unmatched descriptions run as generic tasks. Docstring now matches reality.

**Why**: Documentation inconsistency found in T12 audit pass (EVALUATION_2026-07-10).

## 2026-07-09 — Narrow sentinel-only loop guard (code-review fix)

**Files changed**:
- `src/runner/main.py` — Removed `_is_auto_continued` from the loop guard condition.
  The guard now fires only when the job description IS the sentinel string exactly.
  The previous check (`created_by.startswith("auto-continue:")`) was too broad: any
  auto-continued job that did genuine work and emitted no signal would be stopped at
  `pending_approval`, preventing tasks with 3+ phases from ever reaching phase 3.
  Sentinel-only detection is sufficient because the sentinel job never emits task signals.
- `tests/test_pure_functions.py` — Added `TestAutoContineGuard` (7 cases) and 6
  atlas-redeploy router test parametrize entries.

**Why**: Code review of PR #2 identified the over-broad guard as a BLOCKER.
528 tests pass.

**Side effects**: Multi-phase tasks with 3+ phases now work correctly. Any job whose
description matches the sentinel exactly is still stopped. Any job auto-continued from
the sentinel but doing real work is no longer stopped.

**Gotchas discovered**: None new.

## 2026-07-09 — Auto-continue loop guard in _update_task_after_job

**Files changed**:
- `src/runner/main.py` — `_update_task_after_job` now checks before spawning a
  continuation job: if the finishing job's description IS the auto-continue sentinel
  (`"Continue to the next phase of the plan."`) OR the job was itself created by
  `auto-continue:*`, it stops and moves the task to `pending_approval` instead of
  spawning another continuation. This breaks the infinite loop that occurred when
  single-shot skills (e.g. `atlas-redeploy`) completed without emitting `task_complete`.
- `src/runner/router.py` — Added `atlas-redeploy` routing rules: patterns
  `\bredeploy atlas\b` and `\batlas[- ](redeploy|deploy|restart|update)\b` now resolve
  to the `atlas-redeploy` skill so its system prompt (including `task_complete`
  instructions) is loaded.

**Why**: `/task redeploy atlas` had no router rule → `atlas-redeploy` skill never loaded
→ no `task_complete` signal → auto-continue loop spawned jobs forever. Eight stuck
`active` tasks and three looping sentinel jobs observed in production on 2026-07-09.
See `docs/TROUBLESHOOTING.md` §"web dashboard active task list shows completed jobs"
for the full diagnosis and fix procedure.

**How to verify**: `python3.12 -m pytest tests/ -q` — 515 pass.

## 2026-07-06 — Runner liveness heartbeat

**Files changed**:
- `src/runner/main.py` — `_job_loop` writes `KEY_RUNNER_HEARTBEAT` (Redis) with the
  current ISO timestamp on every iteration. The loop ticks ≤2s normally (BLPOP timeout)
  and keeps ticking while jobs run in the background, so a fresh value means the runner
  is alive. Non-fatal on Redis error.

**Why**: Feeds the meaningful `GET /health` (gateway) and the external heartbeat Worker
(`ops/heartbeat-worker/`) so a dead runner is detectable from off-box. See gateway +
db CHANGELOGs for the same day.

**How to verify**: `redis-cli get heartbeat:runner` returns a recent timestamp while the
runner is up.

## 2026-07-06 — Startup reconciliation of orphaned 'running' jobs

**Files changed**:
- `src/runner/reconcile.py` (new) — `reconcile_orphaned_jobs()` + pure helper
  `orphaned_job_ids()`. On startup, any job still `status='running'` is a leftover
  from a process that died mid-job; each is marked `failed` with a terminal
  `job_failed` audit event (`error_category='orphaned'`).
- `src/runner/main.py` — call `reconcile_orphaned_jobs()` in `main()` after the auth
  check, before starting the loops. Non-fatal on error.
- `src/runner/audit_index.py` — `categorize_error()` now recognises `orphaned` (matches
  "startup reconciliation"/"orphaned") and documents it in the taxonomy.
- `tests/test_orphaned_jobs.py` (new) — 6 pure-function tests.

**Why**: The per-job timeout (`session_timeout_seconds`) only guards jobs the *current*
process runs. A runner killed mid-job (crash, SIGKILL, `launchctl stop`, power loss)
left its Job row in `running` forever — violating INV-2 (missing terminal event) and
making the job look perpetually in-flight to self-diagnose/upkeep. Reconciliation writes
the missing terminal event on next boot.

**Design**: Fail-only, no auto-requeue — a job may have had side effects before the
crash; blindly re-running could double them. **Idempotent**: reconcile checks the job's
audit log for an existing terminal event first — if none, it synthesises `job_failed`
and fails the row; if one already exists (the rare crash *between* writing the event and
committing the DB update), it reconciles the row to that recorded outcome without writing
a second event. This keeps INV-2 at exactly one terminal event across repeated restarts.
Each reconciled job also updates the incremental audit index (mirrors `_finish_job`).

**New invariant**: INV-15 — runner reconciles orphaned `running` jobs on startup before
consuming the queue. Added to `.context/SYSTEM.md`.

**How to verify**: insert a row with `status='running'`, restart the runner, confirm it
flips to `failed` with a `job_failed` audit event categorised `orphaned`;
`pipenv run pytest tests/test_orphaned_jobs.py`.

**Side effects**: None on normal operation (no `running` rows at a clean startup → no-op).

**Files changed**:
- `src/runner/main.py` — Added `_preflight_check()`: validates skill
  resolution (inherits from task if router doesn't match), CWD existence.
  Rewrote `_maybe_escalate()` as a 3-level chain: L1 = higher model/effort,
  L2 = self-diagnose with full audit context, L3 = max-effort last resort.
  Level 3 failure notifies user via tasks:notify.
- `src/runner/session.py` — `format_task_turns()` now expands the last
  assistant turn to 8000 chars (the plan). `_build_task_context()` adds
  explicit "Your instructions for this turn" section with user's last reply.
- `.context/SYSTEM.md` — Added `runner.router` to main.py deps.

**Why**: Continuation jobs were losing context (routed wrong, wrong model,
plan truncated). Failures had no recovery path beyond a single retry.
Now: pre-flight catches misconfigs instantly, continuations inherit their
parent skill, and failures escalate through 3 levels before giving up.

## 2026-04-20 — Router fix: app-patch pattern for project-level requests

**Files changed**: `src/runner/router.py` — Added pattern matching
`fix/update/patch/add/modify/change/upgrade` + `app/project/site/dashboard/page`
so requests like "update the bingo app to add login" route to app-patch.

**Why**: "Update the baseball bingo app..." was falling through to generic
task (no skill resolved) because the existing patterns required technical
nouns like `function`, `endpoint`, etc.

## 2026-04-20 — Multi-turn task interaction with approval flow

**Files changed**:
- `src/runner/session.py` — Added `format_task_turns()` pure helper and
  `_build_task_context()` which loads prior turns from DB and injects a
  "Task conversation" section into the system prompt for continuation jobs.
  Added `_fetch_task_turns()` async helper.
- `src/runner/main.py` — Added `_update_task_after_job()` which runs after
  task-linked jobs complete. Records assistant turns, detects `task_question`
  and `task_complete` audit events, updates task status, and publishes
  notifications via `tasks:notify` Redis channel.

**Why**: Jobs were one-shot with no way to respond to output or approve
completion. Tasks now wrap jobs into multi-turn conversations where the
user can reply and the system continues with full context.

**Side effects**: Every task-linked job now triggers `_update_task_after_job`
after completion (non-fatal). Jobs without `task_id` are unaffected.

## 2026-04-20 — Skill consistency: sections lint, post_review standardization, template

**Files changed**:
- `scripts/lint_docs.py` — New `check_skill_sections()` (8th lint check).
  Non-internal skills must have `## Gotchas` section and body >= 10 lines.
- `skills/TEMPLATE.md` (NEW) — Reference template for skill authors.
  Documents required frontmatter fields, required body sections (Inputs,
  Procedure, Quality gate, Gotchas), optional sections, and conventions.
- `skills/new-skill/SKILL.md` — References TEMPLATE.md as first step.
- `skills/app-patch/SKILL.md`, `skills/new-project/SKILL.md`,
  `skills/new-skill/SKILL.md`, `skills/project-evaluate/SKILL.md` —
  Added explicit `reviewer_model` + `reviewer_effort` to post_review config.
- `skills/code-review/SKILL.md` — Added `## Gotchas` section (was missing).

**Why**: Skill bodies were structurally inconsistent. No template for new
skill authors. Post-review config was implicit except for server-patch.
New lint check catches structural gaps early.

**Side effects**: New lint check (8th) runs on every invocation. Skills
missing Gotchas will be flagged — code-review was the only one.

## 2026-04-20 — Debugging: error categorization, incremental index, failure correlation

**Files changed**:
- `src/runner/audit_index.py` — Added `categorize_error()` pure function
  that classifies error messages into categories (quota, auth, timeout,
  tool_error, network, import_error, schema, unknown). Added
  `error_category` field to `IndexEntry`. Added `append_to_index()` for
  incremental index updates without full rebuild.
- `src/runner/main.py` — `job_failed` audit events now include
  `error_category`. `_finish_job()` calls `append_to_index()` after every
  job completion/failure for real-time index freshness.
- `src/runner/events.py` — Multi-skill failure correlation: if 3+ different
  skills fail within 5 minutes, enqueues a single combined self-diagnose
  with `target_kind: multi-skill` instead of N separate diagnoses.
- `.context/SYSTEM.md` — Added `runner.audit_index` to runner.main deps.

**Why**: Error messages were unstructured text — no aggregation possible.
Audit index was stale between nightly rebuilds. Multi-skill failures
triggered redundant diagnoses instead of surfacing shared root cause.

**Side effects**: Every finished job now appends to INDEX.jsonl (~1ms).
New `error_category` field in audit events and index entries.

## 2026-04-20 — Feedback loops: unified MCP tags, escalation, parent tracking

**Files changed**:
- `src/runner/session.py` — Removed `_NEEDS_PROJECTS_MCP` and
  `_NEEDS_DISPATCH_MCP` hardcoded sets. MCP injection now uses frontmatter
  tags as sole source of truth. Added `parent_job_id` field to `job_started`
  audit log events for child jobs (enables cross-job tracing without DB).
- `skills/review-and-improve/SKILL.md` — Added `needs-projects-mcp` tag
  (was hardcoded only).
- `skills/server-upkeep/SKILL.md` — Added `needs-projects-mcp` tag.
- `skills/server-patch/SKILL.md` — Added `needs-projects-mcp` tag.
- `skills/app-patch/SKILL.md` — Added `escalation.on_failure` (Opus 4.7 / xhigh).
- `skills/new-skill/SKILL.md` — Added `escalation.on_failure` (Opus 4.7 / max).

**Why**: MCP opt-in had a dual source of truth (hardcoded sets + tags).
Now tags-only — single source, auditable in each SKILL.md. app-patch and
new-skill previously hard-failed with no retry; now escalate on failure.
Parent_job_id in audit events enables log-only causality tracing.

**Side effects**: Skills that relied on the hardcoded sets but lacked tags
would break — all 4 have been updated with the correct tags.

## 2026-04-20 — Knowledge surfacing: seed module skills + auto-inject + context_files validation

**Files changed**:
- `.context/modules/runner/skills/GOTCHAS.md` — Seeded with 5 entries from
  Troubleshooting.md and CHANGELOG gotchas (audit_log.append collision,
  _writeback false positives, stuck jobs, SDK version mismatch, import lint).
- `.context/modules/runner/skills/DEBUG.md` — Seeded with 2 entries (8-step
  failure triage order, quota false positive detection).
- `.context/modules/gateway/skills/GOTCHAS.md` — Seeded with 2 entries
  (Telegram done-listener mapping, dashboard 404).
- `.context/modules/hosting/skills/GOTCHAS.md` — Seeded with 5 entries
  (cloudflared TLS, config location, plist args, Python modules, TCC).
- `.context/modules/hosting/skills/DEBUG.md` — Seeded with 2 entries
  (runner restart checklist, cloudflared no connections).
- `.context/modules/db/skills/GOTCHAS.md` — Seeded with 2 entries
  (sqlalchemy.update collision, never edit migrations).
- `src/runner/session.py` — Added `parse_skill_file_entries()` pure helper
  and `_module_knowledge_context()` function. Server-scoped sessions now
  get a "Known issues" section with GOTCHAS/DEBUG entry titles for
  detected modules.
- `src/registry/skills.py` — Added context_files validation at load time.
  Logs warning for missing files.
- `scripts/lint_docs.py` — New `check_context_files_exist()` (7th check).
  Validates all skills' context_files reference real files.
- `skills/idea-generation/SKILL.md` — Removed nonexistent
  `projects/ideas/README.md` from context_files (caught by new lint check).

**Why**: Module skill files were empty stubs — zero institutional knowledge
visible to sessions. Now seeded from Troubleshooting.md + CHANGELOG
gotchas, auto-injected into directives, and context_files are validated.

**Side effects**: Server-scoped sessions mentioning specific modules now
get a slightly larger directive (entry titles only — compact). New lint
check (7th) runs on every lint invocation.

## 2026-04-19 — Tool-use audit in code review (Rec 15)

**Files changed**:
- `src/runner/review.py` — Added `_summarize_tool_usage()` helper that
  reads the parent job's audit log and produces a compact tool-count
  summary (Read: N files, Edit: N, etc.). `run_code_review()` now appends
  this summary to the review prompt. Updated `REVIEW_SYSTEM_PROMPT` to
  include an "Approach" section in the output format.
- `skills/code-review/SKILL.md` — Added Approach section to output format
  description.

**Why**: Per § 7 Rec 15. Code review previously only evaluated the diff.
Now the reviewer also sees how the session arrived at the diff (tool usage
patterns), enabling process quality feedback.

**Side effects**: Every code review that has a parent job ID now reads
the parent's audit log (~1ms overhead). The review prompt is slightly
longer.

## 2026-04-19 — Audit log index (Rec 9)

**Files changed**:
- `src/runner/audit_index.py` (NEW) — `rebuild_index()` builds
  `volumes/audit_log/INDEX.jsonl` from all JSONL audit logs. One line
  per job: `{job_id, skill, model, effort, status, error_first_line,
  keywords}`. `search_index()` queries the index by skill, status, or
  keyword. `build_index_entry()` and `_extract_keywords()` are pure
  and unit-tested.
- `skills/self-diagnose/SKILL.md` — Added audit log index search step
  before drilling into individual logs.
- `skills/server-upkeep/SKILL.md` — Added step 2b to rebuild the index
  during daily upkeep.

**Why**: Per § 7 Rec 9. Self-diagnose previously had to scan individual
audit logs to find similar past failures. The index provides O(1) lookup
by skill/status/keyword.

**Side effects**: `volumes/audit_log/INDEX.jsonl` is created/overwritten
on each rebuild. Not append-only — safe to delete and rebuild.

## 2026-04-19 — Context budget accounting (Rec 8)

**Files changed**:
- `src/runner/session.py` — Added `estimate_context_tokens()`,
  `context_budget_fraction()` pure helpers and `_MODEL_BUDGETS` map.
  `run_session()` now emits `context_budget_used` audit log event with
  estimated tokens, model budget, and fraction before starting the session.
- `src/runner/retrospective.py` — Added `ContextBudget` dataclass,
  `parse_budget_events()` and `aggregate_context_budgets()` pure helpers,
  and `context_budget_report()` function. Walks audit logs for
  `context_budget_used` events and aggregates by skill.
- `src/audit_log.py` — Documented `context_budget_used` event kind.

**Why**: Per § 7 Rec 8. Skills with oversized static context waste tokens
on every run. Now measurable: review-and-improve flags skills using >30%
of the model's context window.

**Side effects**: Every job now emits one extra audit log event
(`context_budget_used`) before the session starts. ~1ms overhead.

## 2026-04-19 — Stale-context warnings in retrospective (Rec 7)

**Files changed**:
- `src/runner/retrospective.py` — Added `StaleContextWarning` dataclass,
  `_newest_mtime()`, `_days_since()` pure helpers, and
  `stale_context_warnings()` function. Checks for CONTEXT.md files >30d
  older than newest source, and CHANGELOG.md files with no updates in 60d
  despite git commits. Synchronous (filesystem + git only).

**Why**: Per § 7 Rec 7. Documentation decay was invisible — now it's a
measurable finding that review-and-improve can propose to fix.

**Side effects**: None on runner execution. Called by review-and-improve
skill during retrospective analysis.

## 2026-04-19 — Project-level protocol reference in directive (Rec 6)

**Files changed**:
- `src/runner/session.py` — `_build_server_directive()` now references
  `.context/PROJECT_PROTOCOL.md` for project-scoped sessions and directs
  to project's `skills/GOTCHAS.md` for non-obvious learnings.

**Why**: Per § 7 Rec 6. Project-scoped sessions lacked a protocol document
analogous to PROTOCOL.md. The new PROJECT_PROTOCOL.md gives them write-back
rules, and the directive now points there.

**Side effects**: None on runner execution — just adds a line to the
project-scoped directive string.

## 2026-04-19 — Graph-walked context injection + import lint (Rec 4)

**Files changed**:
- `src/context/module_graph.py` (NEW) — Pure functions: `parse_module_graph()`
  parses the SYSTEM.md markdown table into a forward dependency map,
  `reverse_graph()` builds the reverse map, `extract_imports()` AST-parses
  Python source for `from src.*` imports, `detect_modules_in_text()` finds
  module references in free-form text, `module_path_to_shorthand()` converts
  file paths to graph shorthands.
- `src/runner/session.py` — `_build_server_directive()` now accepts
  `job_description` and calls `_module_dependency_context()` for server-scoped
  sessions. When the description mentions known modules, the directive includes
  "Module dependencies" section listing dependents and advising to read their
  CONTEXT.md before API changes.
- `scripts/lint_docs.py` — New `check_module_graph_imports()` lint check.
  AST-parses every Python file under `src/`, compares actual imports against
  declared dependencies in SYSTEM.md module graph. Warns on undeclared deps.
- `.context/SYSTEM.md` — Fixed undeclared deps for runner.main, runner.session,
  gateway.web, gateway.telegram_bot, runner.retrospective. Added
  context.module_graph row.
- `tests/test_module_graph.py` (NEW, 23 tests) — Pure-function coverage for
  graph parser, import extractor, module detector, path shorthand conversion.
- `tests/test_doc_lint.py` — Added `test_module_graph_imports` test.

**Why**: Per § 7 Rec 4. Sessions modifying server modules now get automatic
dependency context, and the lint check catches undeclared cross-module imports
before they accumulate.

**Side effects**: The new lint check (6th) runs on every `python3 scripts/lint_docs.py`
invocation. It caught 12 real undeclared deps from prior phases, now fixed.

## 2026-04-19 — Added context consumption rollup (Rec 2)

**Files changed**:
- `src/runner/retrospective.py` — Added `ContextUsage` dataclass,
  `parse_read_events()` pure helper, `_normalize_path()` pure helper,
  and `context_consumption()` async rollup function. Walks audit log
  JSONL files for Read tool_use events, joins against jobs table for
  skill/status/rating, returns per-(skill, file_path) usage metrics.

**Why**: Teaches `review-and-improve` what files are actually useful to
skills by measuring actual Read tool usage from audit logs. Files read in
>50% of a skill's runs should be in `context_files`; files read <10% can
be removed. Per § 7 Rec 2.

**Side effects**: None on runner execution — this module is imported by
the gateway web route and by the review-and-improve skill.

## 2026-04-18 — Added proposals.py helper module (Rec 10)

**Files changed**:
- `src/runner/proposals.py` (NEW, ~230 lines) — pure helpers + async DB
  ops for proposal tracking table. Public interface: `extract_proposal_id`,
  `is_valid_change_type`, `is_valid_outcome`, `format_proposal_line`,
  `find_recent_duplicate`, `insert_proposal`, `mark_proposal_merged`,
  `list_pending_proposals`, `list_recent_proposals`, `get_proposal_by_id_prefix`.

**Why**: Supports the `/proposals` Telegram command + dedup/merge-stamping
in the review-and-improve and server-patch skills per § 7 Rec 10.

**Side effects**: None on runner execution — this module is imported lazily
by the Telegram handler and by skills that need it.

## 2026-04-18 — Added learning extractor post-session hook (Rec 1)

**Files changed**:
- `src/runner/learning.py` (NEW, ~280 lines) — Haiku classifier that runs after each successful non-chat, non-internal job. Pure helpers (`should_extract`, `parse_learning_response`, `format_audit_excerpt`, `list_installed_modules`) + async `extract_learning` (one-turn Haiku call, returns `LearningProposal`) + `maybe_extract_and_enqueue` (full pipeline entry point).
- `src/runner/main.py` — Added import of `maybe_extract_and_enqueue`. Added hook call in `_process_job` after writeback verification. Conditions: skip chat kind, skip any kind starting with `_`, skip internal skills (resolved_skill starts with `_`), skip escalation retries (`escalated_from` flag in payload).
- `skills/_learning_apply/SKILL.md` (NEW, internal skill) — Sonnet 4.6 / low, leading-underscore kind, takes payload from the classifier and appends to `.context/modules/<module>/skills/<CATEGORY>.md` using the `APPEND_ENTRIES_BELOW` marker. Dedup check by title grep before append. Commits locally; does not push.
- `.context/SKILLS_REGISTRY.md` — registered `_learning_apply` as internal skill.
- `.context/SYSTEM.md` — added `src/runner/learning.py` row to module graph.
- `.context/modules/runner/CONTEXT.md` — added `learning.py` to Paths, documented `maybe_extract_and_enqueue` in public interface.
- `tests/test_learning.py` (NEW) — 4 test classes / 27 pure-function tests covering should_extract, parse_learning_response, format_audit_excerpt, list_installed_modules.

**Why**: Closes the F1 feedback loop per `docs/EVALUATION_2026-04-18.md` § 7 Rec 1. Before this, institutional learnings were supposed to be written back by the primary session per PROTOCOL.md, but in practice only 1 PATTERNS.md existed across 5 modules. The classifier runs on every code-touching job and proposes a learning when appropriate; the internal skill applies it. Token-efficient: the `should_extract` gate avoids Haiku calls on read-only/chat jobs.

**Side effects**: Every successful non-chat, non-internal, non-escalation job now runs a ~5s Haiku classification after the existing writeback + review hooks. Classifier failures are logged and swallowed (non-fatal for the primary job). New audit log event kinds: `learning_extraction_done`, `learning_apply_enqueued`. New `_learning_apply` child job kind can appear in the queue.

**Gotchas discovered**: None yet; will accumulate as the loop runs in production. Likely candidates: classifier over-proposing (too lax) or under-proposing (too strict), `_learning_apply` concurrent-write conflicts on the same file.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/runner/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


<!-- Newest entries at top. Every session that modifies src/runner/ appends here. -->

## 2026-04-18 — Context-aware SERVER_DIRECTIVE + context_files frontmatter

**Files changed**:
- `src/runner/session.py` — Replaced static `SERVER_DIRECTIVE` string with `_build_server_directive(skill_cfg, cwd)` function. Three code paths: chat (minimal), project-scoped (targeted), server-scoped (full). Appends `context_files` reading list when declared in skill frontmatter.
- `src/registry/skills.py` — Added `context_files: list[str]` field to `SkillConfig` dataclass. Parsed from SKILL.md frontmatter in `load()`.

**Why**: Reduces wasted tokens. Chat sessions no longer get instructions to read SYSTEM.md. Project-scoped sessions get targeted instructions about the project's CLAUDE.md. Skills can declare which docs their sessions should read first.

## 2026-04-17 — Phase 6: research-deep, idea-generation, project-update-poll, restore skills

**Files created**:
- `skills/research-deep/SKILL.md` — Deep-dive research skill. Opus 4.7 / high, 80 max turns, escalation to xhigh on failure. 10-20 sources, 2000-5000 words, mandatory "Where sources disagree" and "How I researched this" sections. Output to `projects/research-deep/`.
- `skills/idea-generation/SKILL.md` — Idea generation skill. Sonnet 4.6 / medium, 20 max turns. Generates 3-5 novel ideas, deduped against `projects/ideas/history.jsonl`. Supports actionable/speculative/technical-only/product-only styles.
- `skills/project-update-poll/SKILL.md` — Project update polling skill. Haiku 4.5 / low, 4 max turns. Runs a project's `on_update` command from manifest.yml. One retry on failure, no diagnosis.
- `skills/restore/SKILL.md` — Restore from backup skill. Sonnet 4.6 / medium, 30 max turns. Destructive: requires "RESTORE <date>" confirmation, second confirmation for >30 day old backups. Stops services, restores pg_dump + audit logs, restarts.

**Files changed**:
- `src/runner/router.py` — Added routing rule for `restore` skill (pattern: `\brestore\b`). Verified `research-deep` and `idea-generation` rules already exist; no duplicates added.
- `.context/SKILLS_REGISTRY.md` — Moved `research-deep`, `idea-generation`, `project-update-poll`, `restore` from Planned to Installed.

**Scaffolded**:
- `projects/ideas/` — Private ideas storage with CLAUDE.md, .context/CONTEXT.md, .context/CHANGELOG.md, empty history.jsonl. Not git-initialized (skill bootstraps on first run).

**Why**: Phase 6 adds four utility skills. `research-deep` is the heavyweight research path (vs `research-report`'s standard path). `idea-generation` provides creative brainstorming with dedup. `project-update-poll` enables cheap scheduled polling of project update commands. `restore` is the disaster recovery path paired with the `backup` script (Phase 5 planned).

**Side effects**: The `restore` router rule is broad (`\brestore\b`) — any message containing "restore" will route there. This is intentional since restore is a rare, deliberate action. `project-update-poll` has no router rule (triggered only via schedules/payload).

## 2026-04-17 — Phase 5: server-upkeep, server-patch, review-and-improve skills

**Files created**:
- `skills/server-upkeep/SKILL.md` — Daily health audit skill. Sonnet 4.6 / low, 20 max turns. Rotates logs, VACUUMs DB, checks tunnel/project/process health, reports anomalies only (outputs SILENT when all quiet, always reports on Sundays). Tags: scheduled, operations.
- `skills/server-patch/SKILL.md` — Server code modification skill. Opus 4.7 / xhigh, 60 max turns. Always PR-gated via `gh pr create`, never auto-merged. Post-review trigger always (Opus 4.7 / high reviewer). Commit metadata includes Requires-migration, Requires-env-change, Rollback. Tags: server, maintenance, manual-merge-required.
- `skills/review-and-improve/SKILL.md` — Retrospective auditor skill. Opus 4.7 / max, plan mode, 30 max turns. Queries job success rates, ratings, escalation/writeback frequency, code-review outcomes. Proposes structured changes for skills with >25% failure, <3 avg rating, frequent escalation, or 0 runs in 30 days. Dispatches server-patch via enqueue_job MCP. Tags: retrospective, needs-dispatch-mcp.

**Files changed**:
- `.context/SKILLS_REGISTRY.md` — Moved `server-upkeep`, `server-patch`, `review-and-improve` from Planned to Installed.

**Why**: Phase 5 completes the operational autonomy layer. `server-upkeep` handles daily housekeeping without human attention (SILENT output suppresses DMs). `server-patch` is the only path for modifying server code, enforcing branch + PR + human-merge. `review-and-improve` closes the feedback loop by analyzing job data and dispatching improvement patches.

**Side effects**: No `src/` files modified. These are skill definitions only — the runner already supports all required features (post_review, escalation, MCP dispatch, SILENT output).

## 2026-04-17 — Phase 4F: self-diagnose skill + event trigger loop

**Files created**:
- `skills/self-diagnose/SKILL.md` — Diagnose failures with risk classification. Auto-applies very-low/low risk fixes, delegates medium to app-patch (direct push) or server-patch (Phase 5, manual only for now), outputs diagnosis only for high risk. Tags: needs-projects-mcp, needs-dispatch-mcp.
- `src/runner/events.py` — Fourth async task. Polls every 60s. Rule 1: skill failed >= 2x in 10 min → enqueue self-diagnose. Rule 2: project unhealthy > 20 min → enqueue self-diagnose. Deduplication via recent job query.
- `tests/test_events.py` — 14 pure-function tests for `_should_trigger_skill_diagnose` and `_should_trigger_project_diagnose`.

**Files changed**:
- `src/runner/main.py` — Added `event_loop` as fourth async task in `main()`.

**Why**: Automated failure recovery. The event loop detects repeated failures and unhealthy projects, then enqueues self-diagnose jobs without user intervention. Per user decision: app-patch pushes freely, server code changes require Telegram Y/N (delegated to server-patch when it ships in Phase 5).

## 2026-04-17 — Phase 4G: project-evaluate skill + router rule

**Agent task**: Build Module G of Phase 4 -- the `project-evaluate` skill that automates producing manifest.yml + .context/CONTEXT.md for existing projects.

**Files created**:
- `skills/project-evaluate/SKILL.md` -- Skill definition with full procedure for analyzing a project codebase, generating manifest.yml, .context/CONTEXT.md, CLAUDE.md, and .context/CHANGELOG.md. Includes non-destructive overwrite checks via AskUserQuestion.

**Files changed**:
- `src/runner/router.py` -- Added routing rule for `project-evaluate` skill. Pattern matches "evaluate/assess/document/onboard project/app". Placed before the "new project" rules so "evaluate project X" does not fall through.
- `.context/SKILLS_REGISTRY.md` -- Added `project-evaluate` to the Installed table.

**Why**: Projects in `projects/` need standardized documentation (manifest.yml, .context/CONTEXT.md) to be registerable for hosting via `register-project.sh`. This skill automates producing that documentation by analyzing the project's codebase.

**Side effects**: The new router rule introduces four new trigger words (evaluate, assess, document, onboard) followed by "project" or "app". These are distinct from existing triggers and placed before the "new project" rules to avoid conflicts.

## 2026-04-17 — Phase 4E: new-skill meta-skill

**Agent task**: Create Module E of Phase 4 -- the `new-skill` meta-skill that authors new skills from natural-language descriptions.

**Files created**:
- `skills/new-skill/SKILL.md` -- Meta-skill system prompt. Opus 4.7 / high, acceptEdits mode, 30 max turns, post_review always. 10-step procedure covering analysis, overlap check, structural reference, drafting, support files, router rules, registry updates, scheduling, commit, and summary.

**Files changed**:
- `.context/SKILLS_REGISTRY.md` -- Moved `new-skill` from Planned to Installed table.

**Why**: `new-skill` is the self-expansion mechanism: once installed, the server can author additional skills from plain-language descriptions without manual SKILL.md authoring. This completes the meta-skill layer of Phase 4.

**Side effects**: None. No `src/` files were modified -- the router already had `new-skill` rules from a prior session (lines 42-43 in router.py). The skill is purely additive.

## 2026-04-17 — Phase 4D: app-patch skill

**Files created**: `skills/app-patch/SKILL.md`
**Why**: Lets the system patch existing projects via `/task fix <project>: <issue>`. Direct commit + push to main per user decision (no PR gate for project repos). Code review sub-agent runs after every patch via `post_review: { trigger: always }`.

## 2026-04-17 — Phase 4B: in-process MCP servers for projects + dispatch

**Agent task**: Build Module B of Phase 4 — two in-process MCP servers that give skills structured access to the projects registry and job dispatch.

**Files created**:
- `src/runner/mcp_projects.py` — MCP server with four tools: `list_projects`, `get_project`, `read_project_logs`, `restart_project`. Uses `create_sdk_mcp_server()` from the Claude Agent SDK. Pure helpers `_format_project()` and `_read_log_tail()` are separated for testability.
- `src/runner/mcp_dispatch.py` — MCP server with one tool: `enqueue_job`. Wraps `src.gateway.jobs.enqueue_job()` with `created_by="dispatch-mcp"`. Pure helper `_validate_enqueue_args()` separated for testability.
- `tests/test_mcp_tools.py` — 21 pure-function tests covering `_format_project`, `_read_log_tail`, and `_validate_enqueue_args`. No DB, no Redis, no SDK.

**Files changed**:
- `src/runner/session.py` — added MCP server injection in `_build_options()`. Skills opt in via `_NEEDS_PROJECTS_MCP` / `_NEEDS_DISPATCH_MCP` name sets (module-level) or `"needs-projects-mcp"` / `"needs-dispatch-mcp"` tags in SKILL.md frontmatter. MCP servers are passed as a dict to `ClaudeAgentOptions(mcp_servers=...)`.

**Why**: Skills like `self-diagnose` and `review-and-improve` need structured project introspection and the ability to spawn child jobs. MCP servers provide this via typed tool calls rather than ad-hoc Bash/file reads, making skill prompts simpler and more reliable.

**Side effects**:
- Skills in the opt-in sets now receive extra MCP tools in their sessions. These tools are additive and do not affect existing tool access.
- The `enqueue_job` MCP tool creates jobs with `created_by="dispatch-mcp"` for audit trail visibility.

**Gotchas discovered**:
- `ClaudeAgentOptions.mcp_servers` is a `dict[str, McpSdkServerConfig]`, not a list. The server name key must match the name passed to `create_sdk_mcp_server()`.
- The `@tool` decorator's function receives a single `args: dict` parameter with all input fields, not keyword arguments.

## 2026-04-17 — Phase 4 Module A: Code review sub-agent infrastructure

**Agent task**: Add synchronous code-review sub-agent that evaluates diffs after code-touching sessions.

**Files created**:
- `src/runner/review.py` — `run_code_review()` spins up an Opus 4.7 / plan-mode session to review a diff. `_parse_outcome()` extracts LGTM/CHANGES/BLOCKER from the reviewer's first line. `get_git_diff()` helper for extracting diffs. Diff truncated at 50K chars.
- `skills/code-review/SKILL.md` — User-triggerable code review. Plan mode, read-only tools, max 5 turns.
- `tests/test_review.py` — 16 pure-function tests for `_parse_outcome` and `get_git_diff`.

**Files changed**:
- `src/runner/main.py` — Added `_maybe_review()` post-session hook. Runs after successful sessions for skills with `post_review.trigger` set in frontmatter. Gets git diff, runs review, stamps `review_outcome` on the job. If BLOCKER, changes job status to `awaiting_user`.
- `src/runner/router.py` — Added routing rule for `code-review` skill.

**Why**: The code-review sub-agent is the quality gate for all Phase 4 coding skills (`new-project`, `app-patch`, `new-skill`). Skills opt in via `post_review: { trigger: always }` in their frontmatter.

**Side effects**: No existing skills have `post_review` set, so this hook is inert until Phase 4 skills are added. Zero impact on existing behavior.

**Design decisions**:
- Synchronous (blocks parent job), not async child job — because the parent's final status depends on the review outcome.
- Skills must opt in via `post_review.trigger: always` (default is `never`). Keeps the review surface explicit.
- Escalated jobs skip review (prevents reviewing the same diff twice after a failure retry).

## 2026-04-17 — Fix: audit_log.append `kind` argument collision

**Agent task**: Diagnose why all jobs fail immediately with `TypeError: append() got multiple values for argument 'kind'`.

**Files changed**:
- `src/runner/session.py` — renamed `kind=job.kind` keyword argument to `job_kind=job.kind` in the `audit_log.append(job_id, "job_started", ...)` call at line 182. The positional `"job_started"` already fills the `kind` parameter in `audit_log.append(job_id, kind, **fields)`, so passing `kind=` as a keyword collided.

**Why**: This bug broke INV-2 (every job must write `job_started` + terminal event). The crash happened before the audit log file was created, so `volumes/audit_log/` was empty — no jobs could run at all.

**Side effects**: The audit log field name for the job's kind changes from `kind` to `job_kind` in `job_started` events. No downstream code reads this field yet, so no migration needed.

**Gotchas discovered**:
- `audit_log.append(job_id, kind, **fields)` uses `kind` as a positional param name. Never pass `kind=` as a keyword in `**fields` — it collides. Use `job_kind` instead.

## 2026-04-17 — Phase 2: write-back verification + failure escalation + tests

**Agent task**: Complete Phase 2 — ship the `research-report` skill end-to-end with write-back enforcement and model escalation on failure.

**Files changed**:
- `src/runner/writeback.py` (new) — pure-function classifier: given a cwd, returns (needs_writeback, list_of_modified_files). Uses `git status --porcelain --untracked-files=all` so individual files are visible, not just parent directories.
- `src/runner/main.py` — added `_verify_writeback()` called after every successful job (except `chat` and `_writeback` itself); if the session left non-doc changes without touching a CHANGELOG, enqueues a child `_writeback` job linked via `parent_job_id`. Added `_maybe_escalate()` called after job failure: if the skill's frontmatter declares `escalation.on_failure`, enqueues a retry with the escalated model/effort (guarded by `escalated_from` payload to prevent loops).
- `src/runner/session.py` — fixed skill-name resolution: leading underscores preserved (`_writeback` stays `_writeback`), other underscores still become dashes (`research_report` → `research-report`).
- `src/runner/router.py` — reordered rules: `new-skill` pattern now matches before `research-report` so "new skill: daily BTC summary" doesn't route to research via the "summary" keyword.
- `tests/test_pure_functions.py` (new) — 52 tests covering router keyword matching, telegram flag parsing (model aliases, effort/permission validation, unknown flags), and writeback classification (doc vs non-doc paths, git status with and without changelog updates).

**Why**: The write-back protocol is the core mechanism that makes "pick up a project 3 months later" work — but only if it's enforced. Primary sessions may skip it under Opus 4.7's stricter instruction following or because a skill author forgot to include it. The `_verify_writeback` hook spawns a cheap Sonnet-low follow-up exclusively for the CHANGELOG update. Similarly, `on_failure` escalation catches the "Sonnet tried and couldn't; Opus 4.7 / high should" case without over-provisioning on every job.

**Side effects**:
- Every successful non-`chat`, non-`_writeback` job now incurs a ~1-second git-status check. Negligible.
- Failed jobs with a skill that declares `on_failure` will retry automatically — doubling cost for persistent failures. This is the intended trade: one extra escalated attempt is cheaper than the user re-running with flags manually.

**Gotchas discovered**:
- `git status --porcelain` without `--untracked-files=all` collapses new directories to their parent name (`src/` instead of `src/thing.py`). Writeback classification needs file-level visibility.
- Router rule order matters: earlier rules win. When adding a new rule, place it above anything it might conflict with.
- `kind.replace("_", "-")` converts `_writeback` to `-writeback` (bad). Internal skills (leading underscore) need to be preserved as-is.
- Top-level markdown files (README.md, MISSION.md, SERVER.md, CLAUDE.md) must be classified as docs — otherwise editing them would trigger false writeback spawns.

## 2026-04-16 — Initial bootstrap (Phase 1)

**Agent task**: Create the runner module from scratch.

**Files created**:
- `src/runner/main.py` — entry point with 3 async loops (job, scheduler, cancel)
- `src/runner/session.py` — one ClaudeSDKClient session per job; streams to audit log
- `src/runner/router.py` — rule-based keyword → skill matcher (no LLM)
- `src/runner/quota.py` — subscription-quota detection and pause/resume

**Why**: Replace the old `worker.py` (94KB, 9 loops, monolithic) with a thin,
skill-driven runner that delegates all agent logic to the Claude Agent SDK.

**Side effects**: None — this is a new module.

**Gotchas discovered**:
- `update` from SQLAlchemy collides with Telegram's `Update` type. Import as
  `sql_update` in files that handle telegram updates.
- The SDK's Python hooks are partially shell-only in the current version; we
  capture audit events via message-iteration instead, which is robust across versions.
- `ANTHROPIC_API_KEY` silently flips the SDK to API billing — the runner's startup
  check aborts if it's set.
