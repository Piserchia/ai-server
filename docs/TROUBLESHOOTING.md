# TROUBLESHOOTING

Common failure modes and exact debug steps. Add to this as you encounter new
failures in the wild — it's a living document.

> **How this doc is organized**: by failure *symptom*, because that's what you
> have when something breaks. Each symptom maps to one or more root causes with
> specific diagnostics.

---

## Symptom: `jobs.review_outcome` is NULL for every job / post-review "never runs"

### Root cause (fixed 2026-08-05 — keep for the pattern)

`_process_job` post-steps that key on `job.resolved_skill` were reading the
ORM instance loaded BEFORE `run_session`; the session stamps
`resolved_skill` via a separate DB session, so the detached instance never
saw it and `_maybe_review` returned early — for every job since inception
(0/516). Fixed by refetching the Job row after completion. **The pattern to
watch**: any post-step reading a column the session wrote must use the
refreshed instance, not the pre-session one — a stale attr on a detached
instance fails silently, not loudly.

### Diagnostics

```bash
psql assistant -c "SELECT review_outcome, count(*) FROM jobs WHERE
  resolved_skill IN ('app-patch','server-patch','atlas-build') GROUP BY 1;"
# all-NULL after 2026-08-05 deploy = regression; check audit log for
# post_review_skipped events (reason=stale_head is the wrong-diff guard,
# not a regression — it means the canonical ff-sync failed or nothing
# was committed). A blocker/error verdict is a `post_review_flagged` audit
# event + `review_flagged` task DM; the job stays `completed` (post_review
# FLAGS, it does not park — the merge gate is the in-session code-review
# before the push, not this after-the-fact second belt).
```
## Symptom: `_learning_apply` job fails with `error_max_turns: Reached maximum number of turns (6)`

### Root cause

The `_learning_apply` skill has a tight `max_turns: 6` budget. Happy path uses
~5 tool calls (ls → grep marker → date → Edit → git commit). Any exploratory
detour blows the budget. Common trigger: the target module's
`skills/<CATEGORY>.md` is missing the `<!-- APPEND_ENTRIES_BELOW -->` marker.
The skill's own Step 3 says "if the marker is missing, just append at end",
but models often instead wander to check other modules' files and burn the
turn budget.

### Fix

1. Ensure the target file has the marker:
   ```bash
   grep -l APPEND_ENTRIES_BELOW .context/modules/*/skills/*.md
   ```
   If any file is missing from that list, either re-run
   `bash scripts/seed-module-skills.sh` (safe on empty stubs — never
   overwrites existing content) or manually insert
   `<!-- Append entries below this marker. Do not delete the marker. -->`
   followed by `<!-- APPEND_ENTRIES_BELOW -->` near the top of the file,
   before any existing entries.
2. If it recurs even with markers in place, raise `max_turns` in
   `skills/_learning_apply/SKILL.md` (must be committed in the DEV repo, then
   deployed — skill frontmatter is server code).

### Deeper root cause (2026-08-02 update)

Even when the payload includes `module: <name>` and the target file has the
marker, the skill still exhausts its 6-turn budget. Reason: `session.py` passes
only `job.description` as the model's user message (see
`_run_in_process(job_id, job.description, options)` at L881+). The skill's
"Payload you will receive" section is aspirational — the payload dict is used
for internal skill config overrides only. The model must infer `module` from
the description string, which usually forces at least three exploratory
tool calls (`ls .context/modules/`, cat parent summary, `ls skills/`) before
the mandatory read/edit/commit sequence — right at or above the 6-turn cap.

**Fix (medium risk, server-code)**: either

1. Inline the payload into the description at enqueue time in
   `src/runner/learning.py` (e.g., prefix
   `"[module=runner category=GOTCHA] Apply learning: ..."`), or
2. In `session.py`, when the job kind starts with `_` (internal), append a
   `\n\n## Payload\n\n<json>` block to the user prompt so the skill sees
   what it was told to expect, or
3. Raise `max_turns` on `_learning_apply` to 10 (buys headroom but doesn't
   fix the misleading skill prompt).

### Incidents

- `912237f7` (2026-08-01) — target `runner/PATTERNS.md` missing marker.
  Diagnosed by `f13d03a6`.
- `30d66555` (2026-08-02) — target `runner/GOTCHAS.md` HAD marker and payload
  HAD `module=runner`, but the model didn't see the payload and burned turns
  exploring modules. Diagnosed + entry manually applied by self-diagnose
  `6c281518`. This is the "deeper root cause" recurrence — server-code fix now
  warranted.
- `e8b05830` (2026-08-03) — same recurrence. Payload had `module=runner`, target
  file had marker, but the model spent turns 1–2 cat'ing the parent job's
  summary to "discover" the module, then reached the `Edit` on turn 6 and hit
  the wall before the `git commit`. The Edit itself SUCCEEDED — the GOTCHAS
  entry is in-tree at line 17 and will flow via `sync-learnings.sh` to
  `origin/runtime-learnings`. Only the commit step was lost. Diagnosed by
  self-diagnose `64d5cb30`. Server-code fix still pending in dev repo (raise
  `max_turns` to 10 AND inline payload into description at enqueue in
  `src/runner/learning.py`).

---

## Symptom: `/task` submitted, shows "queued", then `failed` quickly with generic error

### Quick triage commands

```bash
cd "$HOME/Library/Application Support/ai-server"

# 1. Find the failed job
psql assistant -c "SELECT id, kind, status, error_message, LEFT(description, 60) AS desc FROM jobs ORDER BY created_at DESC LIMIT 5;"

# 2. Get the full audit log for the failed job
JOB_ID=<paste-full-uuid-from-above>
cat "volumes/audit_log/${JOB_ID}.jsonl" | head -40

# 3. Check the runner's process log at the time of failure
grep -A 5 "${JOB_ID:0:8}" volumes/logs/runner.log | head -40
```

### Root cause #1: Claude Code CLI not logged in

**Diagnostic**: audit log shows `job_failed` within 1–2 seconds with error mentioning auth/credentials.

**Fix**:
```bash
# Run this at the Mac's console (not over SSH without display)
claude login
# Pick your Max plan account, complete browser flow
claude --version   # verify it prints something
```

After login, restart the runner:
```bash
bash scripts/run.sh restart
```

### Root cause #2: `ANTHROPIC_API_KEY` leaked into the environment

**Diagnostic**:
```bash
# Inside the runner's environment:
ps auxww | grep "runner.main" | head -1
# Then look for ANTHROPIC_API_KEY in any shell rc:
grep -rn "ANTHROPIC_API_KEY" ~/.zshrc ~/.zprofile ~/.bashrc ~/.bash_profile ~/.profile 2>/dev/null
```

If any output, remove those lines (`vi` them). The runner's `_check_subscription_auth()` should have aborted with a loud error on startup; if it didn't, the env var got set *after* startup (e.g., by the plist's Environment). Also check:

```bash
cat ~/Library/LaunchAgents/com.assistant.runner.plist | grep -A 2 ANTHROPIC
```

If set there, re-run `bash scripts/install-launchd.sh uninstall && bash scripts/install-launchd.sh`.

### Root cause #3: SDK version mismatch / missing tools

**Diagnostic**: audit log has a `tool_use` event with a tool name, then an immediate `tool_result` with `is_error: true` and a message like "Tool not found" or similar.

**Fix**:
```bash
pipenv run pip show claude-agent-sdk
# Expect: Version: 0.1.60 or higher
# If lower, upgrade:
pipenv install "claude-agent-sdk>=0.1.60"
bash scripts/run.sh restart
```

If the SDK version is current but specific tools (WebSearch, WebFetch) still fail: the subscription tier may not include those tools. On Max 5x and up they should be available. Ping @userinfobot on Telegram to confirm your plan.

### Root cause #4: `projects/research/` bootstrap fails on first run

**Diagnostic**: audit log shows the skill reached the `mkdir -p projects/research` step but then stalled or errored.

**Most likely**: the ai-server repo root has a `.gitignore` rule that excludes `projects/*/`, which is *correct* behavior — the child `projects/research/` git repo is separate from ai-server. But if the Bash tool ran `git add` from the wrong cwd, it won't find anything to commit.

**Fix**: the skill explicitly `cd`'s into `projects/research/` before `git commit`. If that's not happening, it's a skill-prompt bug. Patch `skills/research-report/SKILL.md` to be more explicit:

```
7. Commit the new report. IMPORTANT: this runs git inside the
   projects/research/ directory, which is its OWN git repo (separate from
   ai-server). Always use the subshell form:

       ( cd projects/research && git add . && git commit -m "Research: <title>" )

   Never run `git commit` from the server root for this purpose.
```

### Root cause #5: Claude decided the job was ambiguous and called `AskUserQuestion` but nothing consumed the question

**Diagnostic**: audit log shows `tool_use` with `tool_name: AskUserQuestion`, job status stuck at `running` (not `awaiting_user`), no Telegram prompt arrives.

**Status**: RESOLVED. `AskUserQuestion` was removed from all skills' `required_tools` lists. The `awaiting_user` job status exists in the runner but no skill currently uses it. If a future skill needs interactive clarification, it would need to re-add `AskUserQuestion` to its tools and wire the prompt through Telegram (not yet implemented).

### Root cause #6: `audit_log.append()` `kind` parameter collision

**Diagnostic**: runner.log shows `TypeError: append() got multiple values for argument 'kind'` in `session.py:run_session`. Jobs fail within 1 second. `volumes/audit_log/` is empty (no `.jsonl` files created at all).

**Root cause**: `audit_log.append(job_id, kind, **fields)` takes `kind` as its second positional argument. If any caller also passes `kind=` as a keyword in `**fields`, Python raises `TypeError`. This happened in the `job_started` call: `audit_log.append(job_id, "job_started", ..., kind=job.kind)`.

**Fix**: already applied — renamed the keyword to `job_kind=job.kind`. If you see this pattern elsewhere, use `job_kind` instead of `kind` in `**fields`.

**Prevention**: avoid naming any keyword argument `kind` when calling `audit_log.append()`.

---

## Symptom: job gets stuck in `running` state and never completes or fails

**Diagnostic**:
```bash
# How long has it been running?
psql assistant -c "SELECT id, started_at, NOW() - started_at AS elapsed FROM jobs WHERE status = 'running';"
```

If elapsed > SESSION_TIMEOUT_SECONDS (default 1800s / 30min) and nothing happened: the timeout didn't fire. Likely runner process died or is stuck.

**Fix**:
```bash
bash scripts/run.sh status
# If runner is "not running" but left a stuck row:
psql assistant -c "UPDATE jobs SET status = 'failed', error_message = 'runner crashed' WHERE status = 'running';"
bash scripts/run.sh start
```

Automated stuck-job recovery (`_stuck_task_recovery_loop`) was planned for Phase 5 but deferred. Manual recovery via the SQL command above is the current approach.

---

## Symptom: Telegram bot never DMs the result, even though the job completed

**Diagnostic**:
```bash
# Bot alive?
bash scripts/run.sh status

# Did it subscribe to jobs:done:*?
grep "post_init\|done_listener" volumes/logs/bot.log | tail -10

# Is the mapping intact?
# (It's in-process; if the bot restarted since the job was submitted, the mapping is lost.)
```

**Fix**: if the bot restarted, the `_job_to_chat` mapping is gone. This is a known Phase 1 limitation. Workaround: check the job via `/status <prefix>` in Telegram, or via the dashboard.

Phase 2+ should probably persist this mapping in Redis with a TTL. Open item — track in a `docs/OPEN_ISSUES.md` entry when it matters.

---

## Symptom: Quota pause triggered incorrectly (Claude Code CLI returned an error that wasn't actually a quota issue)

**Diagnostic**:
```bash
redis-cli get quota:paused_until   # if set, we're paused
redis-cli get quota:last_reason    # why we think we're paused

# Find the job that triggered the pause
grep "quota exhausted" volumes/logs/runner.log | tail -5
```

If the "reason" is clearly not a quota issue (e.g., a network error, a bad tool call):

**Fix**:
```bash
# Clear the pause via Telegram:
/resume
# Or manually:
redis-cli del quota:paused_until quota:last_reason
```

Then improve the quota detection in `src/runner/quota.py:detect_quota_error` to not match whatever false-positive string it hit. Update `tests/test_pure_functions.py` with a case for the false positive so it can't regress.

---

## Symptom: `_writeback` child jobs spawning on every job (noisy)

**Diagnostic**:
```bash
psql assistant -c "SELECT kind, COUNT(*) FROM jobs WHERE created_at > NOW() - INTERVAL '1 day' GROUP BY kind;"
# If lots of _writeback jobs compared to other kinds, the verification is over-triggering.
```

**Root cause**: `_is_doc_path` in `src/runner/writeback.py` doesn't recognize a file pattern that should be a doc. Common culprits:

- Python-tooling-generated files (pyproject.toml lockfiles, __pycache__/, .ruff_cache)
- Editor temp files (.DS_Store, .swp)
- Log files that are git-tracked for some reason

**Fix**: extend `_is_doc_path` or add patterns to `.gitignore`. Preferred: `.gitignore` — the files shouldn't be in git status at all.

```bash
echo "__pycache__/" >> .gitignore
echo ".DS_Store" >> .gitignore
echo "*.pyc" >> .gitignore
echo ".ruff_cache/" >> .gitignore
```

Then run:
```bash
git rm -r --cached __pycache__/ .ruff_cache/ 2>/dev/null
git commit -m "Tighten .gitignore to prevent writeback false positives"
git push
```

On the Mac Mini, `git pull` + restart runner. Verify by submitting a chat (shouldn't trigger `_writeback`):
```
/chat hello
```

---

## Symptom: Dashboard shows jobs but `/api/jobs/<id>` returns 404

**Diagnostic**: the prefix matcher (`find_job_by_prefix` in `src/gateway/jobs.py`) requires a unique prefix. If two jobs share the first 8 characters of their UUIDs (extremely unlikely but possible), it returns None for ambiguous.

**Fix**: use the full UUID in the URL, or pass a longer prefix (10+ chars virtually guarantees uniqueness).

---

## Symptom: Runner keeps restarting (launchd throttling kicks in)

**Diagnostic**:
```bash
launchctl list | grep com.assistant
# Look for a non-zero exit status in the third column
```

```bash
tail -100 volumes/logs/runner.err.log
# The actual exception
```

**Common causes**:

1. **Postgres/Redis not running** — `brew services start postgresql@15 redis`
2. **Migration not applied** — `pipenv run alembic upgrade head`
3. **Python imports failing** — missing dep: `pipenv install`
4. **ANTHROPIC_API_KEY set** — see Root cause #2 above
5. **claude CLI missing** — reinstall: `curl -fsSL https://claude.ai/install.sh | bash`

launchd's `ThrottleInterval` is 30s (set in the plist). If it restarts 3+ times in a row, macOS may back off longer. Uninstall and reinstall after fixing:
```bash
bash scripts/install-launchd.sh uninstall
# fix the underlying issue
bash scripts/install-launchd.sh
```

---

## Symptom: "permission denied" errors on file read/write inside `~/Documents/`

**Root cause**: macOS Transparency / Consent / Control (TCC) gates `~/Documents/`, `~/Desktop/`, `~/Downloads/` behind Full Disk Access. This is the bug that broke your old mac-mini-ai-server setup.

**Fix**: move the server out of `~/Documents/`:
```bash
# Stop everything
cd "$(location-of-ai-server)"
bash scripts/run.sh stop
bash scripts/install-launchd.sh uninstall 2>/dev/null || true

# Move
mv "$(location-of-ai-server)" "$HOME/Library/Application Support/ai-server"
cd "$HOME/Library/Application Support/ai-server"

# Update SERVER_ROOT in .env
sed -i.bak 's|.*SERVER_ROOT=.*|SERVER_ROOT=/Users/chris/Library/Application Support/ai-server|' .env
rm -f .env.bak

# Rebuild venv (hardcoded paths inside)
pipenv --rm
pipenv install --dev

# Restart
bash scripts/run.sh start
bash scripts/install-launchd.sh
```

---

## Symptom: Can't figure out what went wrong — where do I look?

Always start here, in this order:

1. `volumes/audit_log/<job_id>.jsonl` — ground truth of what the agent did
2. `volumes/audit_log/<job_id>.summary.md` — if present, Claude's own post-hoc summary
3. `volumes/logs/runner.log` — runner-level events around the job
4. `volumes/logs/runner.err.log` — crashes and stack traces
5. `volumes/logs/bot.log` / `volumes/logs/web.log` — the gateway that submitted it
6. `psql assistant` queries on `jobs` table — state at DB level
7. `redis-cli keys "quota:*"` — quota pause state
8. `launchctl list | grep com.assistant` — process supervisor state

Paste any of these into a Claude Code session along with this file and the
relevant skill's SKILL.md, and it'll usually diagnose in one turn.

---

## Symptom: Telegram handler crashes with "Can't parse entities: can't find end of the entity starting at byte offset N"

**Diagnostic**: `bot.err.log` shows `sendMessage "HTTP/1.1 400 Bad Request"` responses. `@_error_safe` retries once, then self-diagnose fires. The failing handler (e.g. `cmd_jobs`, `cmd_status`) sends a message with `parse_mode="Markdown"`.

### Root cause

The handler interpolates a string containing an unescaped Markdown-special character (`_`, `*`, `` ` ``, `[`) into the outgoing message. Telegram's legacy Markdown parser then treats the character as the start of an entity it can never close. Common culprit: skill/kind names that start with underscore (`_writeback`) inserted without running through `_esc_md()`.

Example offender (`src/gateway/telegram_bot.py:810-813`):

```python
skill = j.resolved_skill or j.kind            # may be "_writeback"
desc = _esc_md(j.description[:40])            # escaped
...
line = f"`{prefix}` {icon} {skill} — {desc}{task_ref}"   # skill NOT escaped
```

When any of the listed jobs has `kind='_writeback'` (or similarly `_`-prefixed), the leading underscore opens an italic run that the parser can't terminate.

### Fix

Wrap every piece of user- or DB-controlled text in `_esc_md()` before it reaches a Markdown-parsed message. In `cmd_jobs`, change:

```python
skill = j.resolved_skill or j.kind
```

to

```python
skill = _esc_md(j.resolved_skill or j.kind)
```

Audit sibling handlers (`cmd_status`, `cmd_tasks`, callback renderers) for the same pattern — anywhere DB text lands inside an f-string with `parse_mode="Markdown"`.

### Prevention

- Treat `_esc_md()` as mandatory for every dynamic value in a Markdown-formatted message, not just `description` fields.
- Alternative: render with `parse_mode=None` for structural messages, reserving Markdown for places where the *formatting* is Claude-authored.
- Consider adding a unit test that asserts each command renderer produces a Markdown-valid payload when given fixture rows whose text includes `_`, `*`, `[`, `` ` ``.

---

## Symptom: self-diagnose fires for a god sentinel job that died with exit code 143 (SIGTERM)

### Diagnostic

Escalation L2 self-diagnose runs with description
`Self-diagnose: job <id> (god) failed. Error: unknown`. The failed job's audit
log ends with `job_failed` carrying
`Command failed with exit code 143 (exit code: 143)` and runner.err.log shows
`claude_agent_sdk._internal.query:Fatal error in message reader: Command failed
with exit code 143`. The job's `description` is the fixed literal
`Continue to the next phase of the plan.` and `created_by` starts with
`auto-continue:<parent-job-id>` — i.e. this was an auto-continue sentinel.

Then check whether a competing user-created job exists for the same task:

```bash
psql assistant -c "SELECT id, kind, status, created_by, LEFT(description,60), started_at
                   FROM jobs WHERE task_id = '<task-id-of-failed-job>'
                   ORDER BY created_at;"
```

If a `god` job with `created_by='telegram:*'` was enqueued in the same minute
(likely a few seconds *before* the sentinel started) and is now `running`, that
job's arrival is almost certainly why the sentinel was killed.

### Root cause

Two defects compose:

1. The **task-hijack sentinel** is the very defect documented in
   `.context/modules/runner/skills/GOTCHAS.md` (2026-07-11 entry
   "Brainstorming clarifying questions get 'Continue to next phase' hijacked").
   The sentinel should never have been enqueued — brainstorming failed to emit
   `task_question`, the runner fell through to auto-continue, and the resulting
   job has no task context.
2. When the sentinel is killed (SIGTERM from the runner because a fresher user
   job arrived, or a manual `/cancel`), the failure path in `main.py`
   unconditionally spawns an L2 self-diagnose child even though the "failure"
   is an intentional cancellation of a hijack job. Self-diagnose then wastes
   turns diagnosing a false positive.

### Fix

**None at the moment.** The sentinel job's death is the desired outcome. The
user's concurrent job (usually a fresh `god` request that explicitly asks about
the same task) is already running and will produce the real answer. Close this
diagnose job with a note. Do **not** attempt to fix the sentinel — it was
correctly euthanised.

### Prevention (requires server-patch)

1. In `_update_task_after_job` (src/runner/main.py, auto-continue branch,
   L676-L709): before enqueuing a sentinel, check whether the task already has
   a queued or running job created by a human channel (`created_by LIKE
   'telegram:%'` or `'web:%'`). If so, skip the sentinel — the user's job will
   drive the task forward.
2. In the L2 escalation path (main.py around L494-L500): skip self-diagnose
   spawn when the failed job's `error_message` starts with
   `Command failed with exit code 143` **and** `created_by LIKE
   'auto-continue:%'`. A SIGTERM'd sentinel is not a defect worth escalating.
3. Longer-term: fix the upstream brainstorming/auto-continue defect so
   sentinels are never enqueued for tasks that were waiting on a clarifying
   question (see the 2026-07-11 GOTCHAS entry for the full plan).

_First occurrence 2026-07-11: job `5ef4d36d` (sentinel for task
`20daab34`), killed 3 minutes into a session where it had correctly
self-identified as the hijack case and was about to fix the defect. User job
`184b480f` (enqueued 36s earlier from Telegram) is the real work; the
escalation into `5f7d8f62` was a false positive._

---

## Symptom: self-diagnose fires for `_evaluate` child of a successful `server-deploy` (exit 143)

### Diagnostic

Escalation L2 self-diagnose runs with description
`Self-diagnose: job <id> (_evaluate) failed. Error: unknown`. The failed
job's `kind` is `_evaluate`, `parent_job_id` points to a `god`/`task` job
whose skill was `server-deploy` and whose summary contains phrases like
"Runner restart is scheduled detached in ~20s". The audit log ends with 1–3
tool_uses (typically reading SYSTEM.md and a `git log`) and then
`job_failed` carrying `Command failed with exit code 143 (exit code: 143)`
within 5–15 seconds of `job_started`. runner.err.log around the same
timestamp shows
`claude_agent_sdk._internal.query:Fatal error in message reader: Command
failed with exit code 143` plus SQLAlchemy pool teardown errors ("attached
to a different loop", "unknown protocol state 3") — the signature of an
in-flight event loop being torn down by a process restart.

### Root cause

`server-deploy` schedules a detached self-restart (~20s after it returns)
so the runner reloads new code. The runner marks the deploy task
successful, then the acceptance evaluator (`_evaluate`) is enqueued as a
child. The evaluator's Claude Agent SDK CLI subprocess is a grandchild of
the runner. When the scheduled restart fires, the runner's process group
is SIGTERM'd — killing the evaluator's CLI subprocess with exit 143. The
failure path in `main.py` unconditionally spawns an L2 self-diagnose on
the "failed" evaluator, producing this false positive.

The parent deploy actually succeeded. No user-visible work was lost.

### Fix

**None required.** Close this diagnose job with a note. Verify the deploy
worked (last commit SHA + healthcheck):

```bash
cd "/Users/alfredbot.ai.butler/Library/Application Support/ai-server" \
  && git log --oneline -3 && curl -sf http://localhost:8081/health
```

If both look right, the deploy succeeded despite the evaluator's death.

### Prevention (requires server-patch)

1. In the L2 escalation path in `src/runner/main.py` (around L494–L500):
   skip self-diagnose spawn when the failed job satisfies all of
   (a) `kind == '_evaluate'`,
   (b) `error_message` starts with `Command failed with exit code 143`,
   (c) the parent job's skill is `server-deploy` (or any skill whose
   post-hook triggers a runner restart).
2. In `server-deploy`: delay the detached restart until after the
   acceptance evaluator has drained, or run the deploy's restart in a
   process group not shared with in-flight child evaluators. The clean
   fix is to make `_evaluate` for `server-deploy` synchronous (run before
   the restart schedule fires) rather than a post-hoc child.
3. Longer-term: `_evaluate` for `server-deploy` is nearly redundant with
   the pytest gate that `server-deploy` itself runs. Consider skipping
   `_evaluate` when the parent skill already declared verified success in
   its summary.

_First occurrence 2026-07-13: job `1719a807` (_evaluate for parent
`a07f46d7`, task "Deploy server"). Parent completed at 18:29:20; evaluator
started same second, died 8s later at 18:29:28 — the runner's own
scheduled restart landed inside the evaluator's session._

---

## Symptom: self-diagnose fires for Telegram handler with error "boom"

**Diagnostic**: incoming self-diagnose job description looks like
`Telegram handler 'handler' failed twice. Error: boom` — the handler name is
literally the identifier `handler` and the error is literally `boom`.

**Root cause (FIXED 2026-07-28)**: `tests/test_telegram_commands.py::TestErrorSafeDecorator::test_exception_retries_then_replies`
was exercising the real `_error_safe` decorator without mocking
`enqueue_job`. The Level-3 branch of `_error_safe` calls
`enqueue_job("Self-diagnose: Telegram handler 'handler' failed twice. Error: boom", kind="self-diagnose", …)`
against the production Postgres `jobs` table, spawning a real self-diagnose
session for every test run. Five zombie rows had accumulated (see
`SELECT id, kind, description FROM jobs WHERE description ILIKE '%handler%boom%'`).
Not a production bot failure — a test-suite leak into production state.

**Fix**: patched `enqueue_job` in that test (commit landing 2026-07-28). Test
now asserts the mock was awaited with `kind="self-diagnose"` instead of
performing the real insertion. All 18 tests in the module still pass.

**Verify no relapse**:
1. `psql assistant -c "SELECT COUNT(*) FROM jobs WHERE description ILIKE '%handler%boom%' AND created_at > NOW() - INTERVAL '1 day';"` after each pytest run — must be 0.
2. If a fresh row appears, grep for `enqueue_job` calls introduced into `tests/` without mocks.
3. `tail volumes/logs/bot.err.log` — should still show only 200 OK responses (real bot health is unrelated).

**Historical note**: earlier revision of this entry hypothesised "human
manually invoked self-diagnose with a synthetic payload" — that was wrong.
The trigger was always the test suite itself. When self-diagnose lands on
a synthetic string, always check `tests/` for real DB calls first.

---

## Symptom: cloudflared tunnel shows "tls: internal error" connecting to Caddy

**Root cause**: Caddy's `tls internal` generates self-signed certs via a local CA. The root cert can't be installed into the macOS trust store without `sudo`, so TLS handshakes fail even with `noTLSVerify: true` in cloudflared config (the error is server-side, not client-side).

**Fix**: Use HTTP between cloudflared and Caddy. The tunnel itself is encrypted end-to-end; the localhost hop doesn't need TLS.

1. Caddyfile and per-project snippets use `http://` prefix (e.g., `http://bingo.chrispiserchia.com`)
2. cloudflared config points to `http://localhost:80` instead of `https://localhost:443`
3. Remove `tls internal` from all Caddy site blocks

**Prevention**: The `setup-caddy.sh` and `register-project.sh` scripts generate `http://` prefixed configs by default.

---

## Symptom: cloudflared system service starts but tunnel has no active connections

**Diagnostic**:
```bash
cloudflared tunnel info ai-server    # "no active connection"
tail -20 /Library/Logs/com.cloudflare.cloudflared.err.log
```

**Common causes**:

1. **Config not at `/etc/cloudflared/`**: The system service runs as root and looks for config at `/etc/cloudflared/config.yml`, not `~/.cloudflared/`. Fix: `sudo cp ~/.cloudflared/config.yml /etc/cloudflared/`
2. **Credentials file not copied**: Also copy the `<tunnel-uuid>.json` file to `/etc/cloudflared/`.
3. **Plist missing `tunnel run` arguments**: The default `cloudflared service install` plist just runs `cloudflared` with no subcommand. It needs `tunnel` and `run` arguments. Fix: `sudo sed -i.bak 's|</array>|<string>tunnel</string><string>run</string></array>|' /Library/LaunchDaemons/com.cloudflare.cloudflared.plist`
4. **Service not started**: Use `sudo launchctl bootstrap system /Library/LaunchDaemons/com.cloudflare.cloudflared.plist` (not the old `launchctl load`).

---

## Symptom: Project launchd service can't find Python modules (`ModuleNotFoundError`)

**Diagnostic**: `tail volumes/logs/project.<slug>.err.log` shows `ModuleNotFoundError: No module named 'flask'` (or similar).

**Root cause**: launchd runs with a minimal PATH. If Python packages were installed via pyenv, the launchd plist needs both `PYENV_ROOT` and pyenv shims in PATH. Using `bash -lc` alone isn't sufficient because bash login shells may not load pyenv's zsh-specific init.

**Fix**: Use the full path to the pyenv python binary in the manifest's `start_command`:
```yaml
start_command: "/Users/<user>/.pyenv/versions/3.12.13/bin/python3 server.py"
```

Or set both env vars in the launchd plist:
```xml
<key>PATH</key>
<string>/Users/<user>/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
<key>PYENV_ROOT</key>
<string>/Users/<user>/.pyenv</string>
```

---

## Symptom: atlas redeploy reports "diverged" / ff-only pull refused in projects/atlas

### Diagnostic
```bash
ATLAS="$HOME/Library/Application Support/ai-server/projects/atlas"
git -C "$ATLAS" status --short && git -C "$ATLAS" remote -v
git -C "$ATLAS" fetch origin
git -C "$ATLAS" log --oneline origin/master..HEAD   # runtime-only commits (the violation)
git -C "$ATLAS" log --oneline HEAD..origin/master   # undeployed dev commits
```

### Root cause
A commit was born in the runtime clone instead of a development clone. The runtime clone
is a pull-only deploy target; any commit made there (hotfix, migration rename, "quick fix
on the Mini") permanently blocks ff-only pulls. First occurrence 2026-07-09: a dbmate
migration-collision repair was committed on the Mini with the host git identity while the
dev repo got its own equivalent commit — same content, different SHAs. Also check
`remote -v`: origin must be `https://github.com/Piserchia/atlas.git` (GitHub-canonical
since 2026-07-31; before that it was the local dev-repo path — a local-path origin is now
itself a misconfiguration).

### Fix
```bash
git -C "$ATLAS" branch backup-$(date +%F)            # preserve, never destroy evidence
git -C "$ATLAS" remote set-url origin https://github.com/Piserchia/atlas.git   # if wrong
git -C "$ATLAS" fetch origin
git -C "$ATLAS" reset --hard <last common commit>    # then: /task redeploy atlas
# afterwards: git log master..backup-<date> — if anything unique, cherry-pick into a
# development clone and land it via origin/master (never re-commit here)
```

### Prevention
GitHub-canonical rule (atlas CLAUDE.md §Deployment topology, 2026-07-31): commits are
born in development clones (Mini `~/Documents/repos/atlas` or a laptop), integrate only
through GitHub `origin/master`, and the runtime clone pulls only. Jobs and skills must
never git-commit in projects/atlas; a fix found on the Mini is committed in a dev clone,
pushed, and deployed via atlas-redeploy. The atlas-redeploy skill emits the divergence
evidence automatically.

## Symptom: a skill-triggered job ignores its skill and does unrelated "helpful" work

### Diagnostic

`resolved_skill` on the job is empty/NULL even though the description starts with a
skill name (`atlas-portfolio: …`). The router (`src/runner/router.py`) has no rule for
that prefix, so the job ran as a GENERIC task: full tool set, server directive only,
and the model free-associated the description against whatever context it found.
First occurrence 2026-07-10: `atlas-portfolio: answer or execute the pending
instruction(s)` — a generic session read the atlas dev repo's feature plan, decided
"pending instructions" meant the plan's pending work package, and implemented it
(committing to the dev repo) instead of recording the owner's sale. The commit was
plausible-looking and even passed tsc while hiding a runtime SQL error.

### Fix

Enqueue skill jobs by **kind**, not description-prefix: `POST /api/jobs
{"kind": "atlas_portfolio", "description": "atlas-portfolio: <the instruction>"}`.
`_resolve_skill` maps kind `foo_bar` → skill `foo-bar` deterministically, the SKILL.md
becomes the session's system prompt, and `resolved_skill` is populated for the audit
trail. The atlas web routes for portfolio-chat do this now.

### Prevention

Any new web/gateway trigger for a skill must pass `kind`. The older atlas-chat
description-routed triggers survive on the specificity of their descriptions —
migrate them to `kind` whenever touched. Vague descriptions ("the pending
instruction(s)") are prompt-injection surface for generic sessions: keep the actual
instruction in the description.

## Symptom: chrispiserchia.com landing page shows "Failed to load projects." (public API 502)

### Diagnostic

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://chrispiserchia.com/api/projects/public   # 502
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/api/projects/public       # 000 → gateway down
launchctl list | grep -E 'com.assistant.(web|runner|bot)$'   # PID column "-", status 0 → stopped, clean exit
tail "/Users/alfredbot.ai.butler/Library/Application Support/ai-server/volumes/logs/runner.out.log"
# → "shutdown signal received" as the last line, no startup after
```

The landing page's JS fetches `/api/projects/public`; any fetch failure renders the
"Failed to load projects." tile. Caddy serving the static page (200) while `/api/*`
502s means Caddy and the tunnel are fine and only the FastAPI gateway on :8080 is down.

### Root cause

The service plists use `KeepAlive: {SuccessfulExit: false, Crashed: true}` — launchd
only restarts crashes. uvicorn, the runner, and the bot all trap SIGTERM and exit **0**,
so anything that stops them gracefully (`launchctl unload`/`stop`, e.g. a re-run of
`scripts/install-launchd.sh` whose subsequent `load -w` didn't relaunch the jobs)
leaves them down permanently with a clean-looking status. First occurrence 2026-07-13
09:30: an incident-cleanup session re-ran `install-launchd.sh`; all three core services
stopped at 09:30:49 and stayed down ~4.5h until manually kickstarted.

### Fix

```bash
UID_N=$(id -u)
launchctl kickstart gui/$UID_N/com.assistant.web
launchctl kickstart gui/$UID_N/com.assistant.runner
launchctl kickstart gui/$UID_N/com.assistant.bot
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8080/health   # expect 200
```

(Safe synchronously from a dev-machine shell; from **inside** a runner job the runner
kickstart must be detached — see `skills/server-deploy/SKILL.md`.)

### Prevention

After any `install-launchd.sh` run or manual unload/stop, verify with
`launchctl list | grep com.assistant` that web/runner/bot have PIDs, and hit
`http://localhost:8080/health`. Prefer `launchctl kickstart -k` for restarts —
it never leaves the job in the stopped-but-loaded state. The external heartbeat
worker (`ops/heartbeat-worker/`) alerts on `/health` going dark; if you got that
alert plus a "Failed to load projects" page, start here.

## Symptom: a job's audit log shows `guard_denied` events / a session complains a tool call was "denied by hook"

### Diagnostic

```bash
cd "$HOME/Library/Application Support/ai-server"
JOB_ID=<uuid>
grep guard_denied "volumes/audit_log/${JOB_ID}.jsonl" | python3 -m json.tool
```

### Root cause

Working as designed (2026-07-27, INV-17): workspace-tier sessions run under
PreToolUse guard hooks (`src/runner/guards.py`) that deny (a) file writes
outside the per-job workspace clone and (b) dangerous Bash — `sudo`,
`launchctl`, keychain reads, force-push, `killall`/`pkill`, `crontab`,
`ANTHROPIC_API_KEY` injection, and destructive commands referencing protected
roots (live checkouts, `~/.claude`, `~/.ssh`, LaunchAgents). These replaced
the docker container lane and bind even under `bypassPermissions`.

### Fix

Usually none — the denial is the isolation model doing its job, and the
session should adapt (work inside its clone; ship via `git push`). It's a
real defect only when a legitimately in-workspace action was denied
(e.g. an over-broad denylist regex): reproduce with
`pipenv run python -c "from src.runner.guards import bash_violation; ..."`,
fix the predicate in `src/runner/guards.py`, and extend
`tests/test_guards.py` with the false-positive case.

### Prevention

Keep guard predicates pure and covered by tests — `tests/test_guards.py` is
the enforcement contract for INV-17.

## Symptom: runner down, `launchctl list` shows no PID with last exit 0; queue not draining; web/bot fine

### Diagnostic

```bash
launchctl list | grep com.assistant          # runner: "-  0  com.assistant.runner"
tail -30 "~/Library/Application Support/ai-server/volumes/logs/runner.err.log"
```

Look for `runner subsystem exited unexpectedly — shutting down for restart`
right after `runner starting`. Kickstarting reproduces it within ~1s:
`launchctl kickstart gui/$(id -u)/com.assistant.runner`.

### Cause

Two interacting behaviors (2026-07-30 incident):
1. A **startup crash in a supervised subsystem** — that night, structlog-style
   kwargs on a stdlib logger in `events.py` (`TypeError: Logger._log() got an
   unexpected keyword argument`), fatal the moment `event_loop` started.
2. The supervisor shut the process down but **exited 0**, and the plists use
   `KeepAlive: {SuccessfulExit: false, Crashed: true}` — launchd never
   restarts a successful exit, so the runner stayed down silently (web /health
   stays green; nothing watched runner liveness).

### Fix

Fix the crashing subsystem (deploy the code fix), then
`launchctl kickstart gui/$(id -u)/com.assistant.runner`. Stranded `queued`
job rows whose Redis entries are gone (`redis-cli llen jobs:queue` = 0 while
rows say queued) never run — cancel them with a note.

### Prevention

Both halves are now structural: `main()` exits **1** on the crash path (so
launchd actually restarts a crashed runner), and lint check 13
(`check_logger_style`) bans structlog-kwargs-on-stdlib-logger repo-wide.
Runner liveness is watched twice: web `/health` returns **503 when the
runner heartbeat is stale** (the external dead-man's-switch alerts on
non-200; worker activated 2026-07-30), and `healthcheck-all.sh` adds a
tunnel-independent local layer (2026-07-31): heartbeat stale AND no runner
PID → direct Telegram DM, rate-limited to one per 30 min.

## Symptom: self-diagnose fires "project 'X' unhealthy for 20+ min" but the project is actually up

### Diagnostic

```bash
# 1. Direct probe — do NOT trust projects.last_healthy_at alone
curl -s -o /dev/null -w "%{http_code} in %{time_total}s\n" http://localhost:<port>/<healthcheck_path>

# 2. Check last_healthy_at age vs. current healthcheck cadence
psql assistant -c "SELECT slug, last_healthy_at, NOW() - last_healthy_at AS age FROM projects WHERE slug='<slug>';"

# 3. Confirm process is alive
launchctl list | grep com.assistant.project.<slug>
```

If `/` returns 200 and processes have PIDs but `last_healthy_at` is old, the
event trigger is a **false positive**: `events._check_project_health` fires off
the DB timestamp alone, and `healthcheck-all.sh` (the script that refreshes it)
slipped its 5-min launchd cadence. Common causes of slippage: the Mac was in
low-power/sleep, the machine was under load, or a prior healthcheck-all took
long enough to push the next tick out.

### Root cause

The `_check_project_health` event trigger in `src/runner/events.py` uses
`projects.last_healthy_at` as its sole liveness signal. That timestamp is only
written by `scripts/healthcheck-all.sh` on its 5-min launchd cadence. When the
cadence slips past 20 minutes for any reason — most often macOS power/sleep
throttling on the Mini — the trigger fires even though the project is fine.
Diagnose costs ~1 Opus session and (worse) any auto-remediation would cause
real downtime for nothing.

### Fix

None operationally — verify with the direct curl probe above, append a
recurrence note here, close the diagnose job. Do **not** restart the project;
that would cause the only actual downtime of the incident.

### Prevention (requires server-patch)

1. Gate the event trigger on a fresh **direct probe** inside
   `_check_project_health`: if the project responds 2xx to its healthcheck path
   within a short timeout, skip the diagnose spawn and refresh
   `last_healthy_at` in-line.
2. Alternatively, add a Redis key `healthcheck:last_run` written by
   `healthcheck-all.sh` on each tick; if that key is older than ~10 min, the
   whole freshness signal is untrustworthy and the trigger should back off.
3. Consider raising `caffeinate`/`pmset` guarantees for the healthcheck plist
   or move the probe in-process (runner-side) so it can't be throttled by
   launchd sleep behavior.

_Recurrences: 2026-07-31 00:24Z, 05:11Z; 2026-08-01 (job `dc1046d6`);
2026-08-02 05:32Z (job `a480b1ee`, atlas answered 200 in 18ms, `last_healthy_at`
23s old at diagnosis time); 2026-08-02 later (job `70196d4c`, baseball-bingo
answered `/healthz` 200 in <1ms, `last_healthy_at` age 20m30s at diagnosis —
`healthcheck-all.sh` cadence slipped); 2026-08-02 11:56Z (job `a38ce894`,
atlas answered `/` 200 in 72ms, `last_healthy_at` age 20m22s at diagnosis —
same cadence-slip signature, healthcheck-all last tick 07:35 local, all three
atlas launchd processes healthy with PIDs); 2026-08-02 ~13:13Z (job
`81efdc40`, baseball-bingo answered `/healthz` 200 in 7ms, `last_healthy_at`
age 21m48s at diagnosis — healthcheck-all last tick 08:51 local, project
PID 71682 healthy); 2026-08-02 ~13:13Z (job `eb3cca84`, atlas answered `/`
200 in 78ms on port 8791, `last_healthy_at` age 21m52s at diagnosis —
`healthcheck.out.log` last write 08:51 local matching the timestamp, all
three atlas launchd processes healthy with PIDs 24233/81428/81432); 2026-08-02
~14:51Z (job `0e350c5b`, baseball-bingo answered `/healthz` 200 in 5.8ms,
`last_healthy_at` age 34m31s at diagnosis — `healthcheck.out.log` last write
10:16 local matching the DB timestamp, project PID 71682 healthy); 2026-08-02
~14:51Z (job `7a6b6f32`, atlas answered `/` 200 in 60ms on port 8791,
`last_healthy_at` age 34m23s at diagnosis — `healthcheck.out.log` last tick
14:16Z (35 min stale, cadence had paused), all three atlas launchd processes
healthy with PIDs 24233/81428/81432; healthcheck-all kickstarted inline and
resumed at 14:51Z); 2026-08-02 ~16:18Z (job `386fd41d`, baseball-bingo
answered `/healthz` 200 in 5.8ms, `last_healthy_at` age 20m42s at diagnosis
— healthcheck-all last tick 15:57:54Z (exactly 20-min slip past the 5-min
cadence), project PID 71682 healthy; healthcheck-all kickstarted inline and
resumed at 16:18:53Z); 2026-08-02 ~16:18Z (job `32dd1e8c`, atlas answered
`/` 200 in 79ms on port 8791, `last_healthy_at` age 20m40s at diagnosis —
same 15:57:54Z last tick as the concurrent baseball-bingo diagnose, all
three atlas launchd processes healthy with PIDs 24233/81428/81432;
healthcheck-all kickstarted inline (shared with concurrent diagnose) and
resumed at 16:19:12Z); 2026-08-02 ~17:10Z (job `93497f75`, atlas answered
`/` 200 in 69ms on port 8791, `last_healthy_at` age 36m03s at diagnosis —
`healthcheck.out.log` last tick 16:34:17Z matching the DB timestamp exactly
(36-min slip past the 5-min cadence, i.e. six missed ticks in a row), all
three atlas launchd processes healthy with PIDs 24233/81428/81432;
healthcheck-all kickstarted inline and resumed at 17:10:33Z); 2026-08-02
~17:10Z (job `db910324`, baseball-bingo answered `/healthz` 200 in 8.4ms,
`last_healthy_at` age 35m58s at diagnosis — same 16:34:17Z last tick as the
concurrent atlas diagnose above (the 5-min cadence had missed six ticks in a
row), project PID 71682 healthy; healthcheck-all kickstart shared with the
concurrent atlas diagnose and resumed at 17:10:33Z / 17:10:44Z); 2026-08-02
~17:57Z (job `a34e2db8`, atlas answered `/` 200 in 88ms on port 8791,
`last_healthy_at` age 21m04s at diagnosis — `healthcheck.out.log` last tick
17:35:54Z matching the DB timestamp exactly (21-min slip past the 5-min
cadence, i.e. four missed ticks in a row), all three atlas launchd processes
healthy with PIDs 24233/81428/81432; healthcheck-all kickstarted inline and
resumed at 17:57:09Z); 2026-08-02 ~17:58Z (job `67d9a2bc`, baseball-bingo
answered `/healthz` 200 in <10ms, `/` and `/static/app.js` both 200 as well,
`last_healthy_at` age ~20m43s at diagnosis — `healthcheck.out.log` last tick
17:35:54Z matching the DB timestamp exactly (same 21-min slip / four missed
ticks signature), project PID 71682 healthy; healthcheck-all had already
self-resumed at 17:57:09Z by the time the diagnose ran — no inline kickstart
needed. Notable: this fires at the same cadence as the concurrent atlas
diagnose in the entry immediately above; both projects share one healthcheck
cadence, so every slip pings the diagnose skill twice); 2026-08-02 ~20:11Z
(job `e38f595c`, atlas answered `/` 200 in 67ms on port 8791,
`last_healthy_at` age 33m19s at diagnosis — `healthcheck.out.log` last tick
19:37:42Z (six missed 5-min ticks in a row), all three atlas launchd
processes healthy with PIDs 24233/81428/81432; healthcheck-all kickstarted
inline and resumed at 20:11:21Z, atlas `last_healthy_at` refreshed to 5s
old); 2026-08-02 ~20:11Z (job `018fbae0`, baseball-bingo answered `/healthz`
200 in 7.6ms and `/` 200 in 3.7ms on port 8790, `last_healthy_at` age
33m30s at diagnosis — same 19:37:42Z last tick as the concurrent atlas
diagnose immediately above (six missed 5-min ticks in a row), project PID
71682 healthy; healthcheck-all kickstart shared with the atlas diagnose,
cadence resumed at 20:11:41Z — reinforcing that every cadence slip pings
both projects' diagnose skills simultaneously); 2026-08-02 ~20:57Z (job
`663d66ab`, baseball-bingo answered `/healthz` 200 in 4.7ms and `/` 200
in 4.1ms on port 8790, `last_healthy_at` age 20m27s at diagnosis —
`healthcheck.out.log` last tick 20:36:51Z matching the DB timestamp
exactly (20-min slip / four missed 5-min ticks in a row), project PID
71682 healthy; healthcheck-all kickstarted inline via
`gui/$(id -u)/com.assistant.healthcheck-all` and resumed at 20:57:41Z,
baseball-bingo `last_healthy_at` refreshed to 3s old — note the launchd
label is `com.assistant.healthcheck-all` not `com.assistant.healthcheck`);
2026-08-02 ~20:57Z (job `45e2dc1b`, atlas twin of the baseball-bingo
diagnose immediately above — atlas answered `/` 200 in 62ms on port
8791, `last_healthy_at` age 20m29s at diagnosis — same 20:36:51Z last
tick / four missed 5-min ticks signature, all three atlas launchd
processes healthy with PIDs 24233/81428/81432; healthcheck-all kickstart
shared with the concurrent baseball-bingo diagnose, atlas
`last_healthy_at` refreshed to 2s old at 20:57:56Z — twentieth
recurrence and the ninth in the last ~24h, still a twin-fires-per-slip);
2026-08-02 ~21:36Z (job `8a7afcaf`, atlas answered `/` 200 in 22ms on
port 8791, `last_healthy_at` age was stale then refreshed to 9s old by
the time diagnosis ran — `healthcheck.out.log` gap 21:13:06Z → 21:36:51Z
(23-min slip past the 5-min cadence, i.e. four missed 5-min ticks in a
row), all three atlas launchd processes healthy with PIDs
24233/81428/81432; healthcheck-all had already self-resumed at 21:36:51Z
before the diagnose ran — no inline kickstart needed. Twenty-first
recurrence); 2026-08-02 ~21:36Z (job `84d10de1`, baseball-bingo twin of
the atlas diagnose immediately above — baseball-bingo answered
`/healthz` 200 in 1.4ms and `/` 200 in 4.0ms on port 8790,
`last_healthy_at` age 23m45s at diagnosis fire, refreshed to 13s old by
the time the direct probe ran — same 21:13:06Z → 21:36:51Z gap / four
missed 5-min ticks signature as the concurrent atlas diagnose, project
PID 71682 healthy; healthcheck-all self-resumed 4s AFTER the diagnose
fired (21:36:47Z fire → 21:36:51Z tick), no inline kickstart needed.
Twenty-second recurrence — twin-fires-per-slip pattern continues, both
projects share one cadence so every slip pings the diagnose skill
twice); 2026-08-02 ~22:17Z (job `4a4e86d8`, atlas answered `/` 200 in
9ms on port 8791, `last_healthy_at` age 3s at diagnosis — refreshed to
current by the time direct probe ran; `healthcheck.out.log` gap
21:56:59Z → 22:17:35Z (20-min slip / four missed 5-min ticks in a row),
all three atlas launchd processes healthy with PIDs
24233/81428/81432; healthcheck-all had already self-resumed at
22:17:35Z before diagnosis ran — no inline kickstart needed. Twenty-third
recurrence — atlas-only fire this time, no concurrent baseball-bingo
twin observed); 2026-08-02 ~22:18Z (job `d0c9f6de`, baseball-bingo
twin of the atlas diagnose immediately above that was reported as
"atlas-only" — the twin *was* enqueued but its diagnose skill loaded a
moment later. baseball-bingo answered `/healthz` 200 in 0.9ms and `/`
200 in 4.2ms on port 8790, `last_healthy_at` age 3s at diagnosis time —
same 21:56:59Z → 22:17:35Z gap / four missed 5-min ticks signature as
the concurrent atlas diagnose above, project PID 71682 healthy;
healthcheck-all had already self-resumed at 22:17:35Z, no inline
kickstart needed. Twenty-fourth recurrence — twin-fires-per-slip pattern
DID hold this slip; the atlas entry's "atlas-only" note above was
written before this baseball-bingo diagnose reported in); 2026-08-02
~23:39Z (job `16b3576e`, baseball-bingo answered `/healthz` 200 in
12.2ms and `/` 200 in 3.2ms on port 8790, `last_healthy_at` age
20m53s at diagnosis — `healthcheck.out.log` gap 23:18:06Z →
23:39:14Z (21-min slip past the 5-min cadence, i.e. four missed
5-min ticks in a row), project PID 71682 healthy; healthcheck-all
kickstarted inline via `gui/$(id -u)/com.assistant.healthcheck-all`
and resumed at 23:39:14Z, both baseball-bingo and atlas
`last_healthy_at` refreshed to ~8s old. Twenty-fifth recurrence —
this fire was baseball-bingo-only in the dispatch window; no
concurrent atlas twin observed this slip); 2026-08-02 ~23:38Z (job
`4d1f4963`, atlas answered `/` 200 in 63ms on port 8791,
`last_healthy_at` age 74s at diagnosis — same 23:18:06Z → 23:39:14Z
cadence-slip signature as the baseball-bingo entry immediately above,
all three atlas launchd processes healthy with PIDs
24233/81428/81432 and `state = running`; healthcheck-all self-resumed
at 23:39:14Z ~31s AFTER this diagnose was enqueued. **The prior entry
above claimed "no concurrent atlas twin observed"; this IS that
twin** — the trigger dispatch window straddled the slip so atlas fired
32s later. Twenty-sixth recurrence); 2026-08-03 ~00:21Z (job
`f74b7415`, baseball-bingo answered `/healthz` 200 in 8.5ms and `/`
200 in 3.1ms on port 8790, `last_healthy_at` age 21m43s at diagnosis
— `healthcheck.out.log` last tick 23:59:21Z (21-min slip past the
5-min cadence, i.e. four missed 5-min ticks in a row), project PID
71682 healthy; healthcheck-all kickstarted inline via
`gui/$(id -u)/com.assistant.healthcheck-all` and resumed at
00:21:19Z, baseball-bingo `last_healthy_at` refreshed to 3s old.
Twenty-seventh recurrence — baseball-bingo-only in the dispatch
window; no concurrent atlas diagnose was enqueued for this slip);
2026-08-03 ~00:20Z (job `9fc8f94a`, atlas twin of the baseball-bingo
diagnose immediately above that was reported as "baseball-bingo-only"
— the atlas twin *was* enqueued; its diagnose loaded a moment later.
Atlas answered `/` 200 in 72ms on port 8791, `last_healthy_at` age
21m32s at diagnosis — same 23:59:21Z last tick / four missed 5-min
ticks signature as the concurrent baseball-bingo diagnose above, all
three atlas launchd processes healthy with PIDs 24233/81428/81432
and `state = running`; healthcheck-all had already been kickstarted
by the concurrent baseball-bingo diagnose so no second kickstart was
needed, atlas `last_healthy_at` refreshed to 2s old at 00:21:22Z.
Twenty-eighth recurrence — the prior "baseball-bingo-only" note above
was written before this atlas diagnose reported in; twin-fires-per-slip
pattern still holds); 2026-08-03 ~02:14Z (job `5356ea20`, atlas answered
`/` 200 in 37ms on port 8791, `last_healthy_at` age 17s at diagnosis —
refreshed to current by the time direct probe ran; `healthcheck.out.log`
gap 01:52:33Z → 02:13:26Z (21-min slip past the 5-min cadence, i.e.
four missed 5-min ticks in a row), all three atlas launchd processes
healthy with PIDs 24233/81428/81432; healthcheck-all had already
self-resumed at 02:13:26Z before diagnosis ran — no inline kickstart
needed. Twenty-ninth recurrence — atlas-only fire in the dispatch
window at diagnosis time; no concurrent baseball-bingo twin observed);
2026-08-03 ~02:33Z (job `617fca69`, atlas answered `/` 200 in 63ms on
port 8791, `last_healthy_at` age 84s at diagnosis — refreshed to
current by the time direct probe ran; `healthcheck.out.log` gap
01:52:33Z → 02:13:26Z → 02:33:48Z (two consecutive slips: first a
21-min gap / four missed 5-min ticks, second a 20-min gap / four
missed 5-min ticks), all three atlas launchd processes healthy with
PIDs 24233/81428/81432; healthcheck-all had already self-resumed at
02:33:48Z (7s AFTER this diagnose was enqueued at 02:33:41Z) — no
inline kickstart needed. Thirtieth recurrence — atlas-only fire in the
dispatch window at diagnosis time; no concurrent baseball-bingo twin
observed for this slip); 2026-08-03 ~02:33Z (job `a6ab792e`,
baseball-bingo answered `/healthz` 200 on port 8790, `last_healthy_at`
age 90s at diagnosis time (02:33:48Z stamp vs 02:35:18Z probe) —
**this IS the concurrent baseball-bingo twin of atlas job `617fca69`
above**; both diagnoses enqueued at 02:33:41Z, but this baseball-bingo
diagnose loaded later so the entry immediately above (Thirtieth
recurrence) was written before this twin reported in and its
"atlas-only fire ... no concurrent baseball-bingo twin observed" note
was premature. Project PID 71686 up 4 days without restart, uvicorn
process healthy; historical anyio `TaskHandle` ImportError in
`project.baseball-bingo.err.log` is from PID 3619 pre-restart 2026-07-30
and no longer relevant. healthcheck-all kickstarted inline via
`gui/$(id -u)/com.assistant.healthcheck-all` (baseball-bingo
`last_healthy_at` refreshed to 3s old at 02:36:31Z). Thirty-first
recurrence — twin-fires-per-slip pattern still holds); 2026-08-03
~03:27Z (job `29089bda`, atlas answered `/` 200 in 33ms on port
8791, `last_healthy_at` age 16s at diagnosis — refreshed to current
by the time direct probe ran; `healthcheck.out.log` gap 03:06:43Z →
03:26:53Z (20-min slip past the 5-min cadence, i.e. four missed
5-min ticks in a row), all three atlas launchd processes healthy
with PIDs 24233/81428/81432; healthcheck-all had already
self-resumed at 03:26:53Z before diagnosis ran — no inline
kickstart needed. Thirty-second recurrence — atlas-only fire in
the dispatch window at diagnosis time; no concurrent baseball-bingo
twin observed); 2026-08-03 ~03:26Z (job `f5728984`, baseball-bingo
twin of the atlas diagnose immediately above that was reported as
"atlas-only" — the twin *was* enqueued (11ms earlier at 03:26:50.28Z
vs atlas 03:26:50.29Z), its diagnose skill just loaded a moment
later. baseball-bingo answered `/healthz` 200 in 1.3ms and `/` 200
in 3.6ms on port 8790, `last_healthy_at` age 11s at diagnosis —
refreshed to current by the time direct probe ran; same 03:06:43Z →
03:26:53Z gap / four missed 5-min ticks signature as the concurrent
atlas diagnose above, project PID 71682 healthy; healthcheck-all
had already self-resumed at 03:26:53Z, no inline kickstart needed.
Thirty-third recurrence — the atlas entry's "atlas-only" note above
was written before this baseball-bingo diagnose reported in;
twin-fires-per-slip pattern still holds); 2026-08-03 ~05:28Z (job
`bcedfdd5`, baseball-bingo answered `/healthz` 200 in 1.8ms and `/`
200 in 6.9ms on port 8790, `last_healthy_at` age 84s at diagnosis —
refreshed to current by the time direct probe ran; `healthcheck.out.log`
gap 03:57:12Z → 05:07:09Z (70-min slip past the 5-min cadence, i.e.
**thirteen** missed 5-min ticks in a row — longest slip observed so
far), then another 20-min gap 05:07:09Z → 05:27:58Z (four more missed
ticks), project PID 71682 healthy; healthcheck-all self-resumed at
05:27:58Z before diagnosis ran — no inline kickstart needed.
Thirty-fourth recurrence — baseball-bingo-only fire in the dispatch
window at diagnosis time; no concurrent atlas diagnose observed for
this slip. Notable: the 70-min gap is roughly double the previous
longest (~36 min); the `events.py` live-probe gate spec at the bottom
of this section is still un-landed).
2026-08-03 ~04:32Z (job `aa522b99`, atlas answered `/` 200 in 48ms
on port 8791, `last_healthy_at` age 2m49s at diagnosis — refreshed
to current by the time direct probe ran; `healthcheck.out.log` gap
03:57:12Z → 05:07:09Z (**70-min slip, thirteen missed 5-min ticks
in a row — ties the prior longest slip observed one hour earlier**)
then another 20-min gap 05:07:09Z → 05:27:58Z, all three atlas
launchd processes healthy with PIDs 24233/81428/81432;
healthcheck-all had already self-resumed at 05:27:58Z (~55 min
AFTER this diagnose was enqueued at 04:32:56Z, which explains why
`last_healthy_at` was already fresh by the time the diagnose skill
actually loaded). Thirty-fifth recurrence — atlas-only fire in the
dispatch window at diagnosis time; no concurrent baseball-bingo
twin observed. Notable: second 70-min slip in ~1h, likely macOS
sleep/power throttling on the Mini through the early-morning
window; still the same signature, still no prevention patch landed).
2026-08-03 ~05:27Z (job `bdc87c02`, atlas answered `/` 200 in
47ms on port 8791, `last_healthy_at` age 4m17s at diagnosis —
already refreshed to fresh by the time the diagnose skill loaded;
`healthcheck.out.log` gap 03:57:12Z → 05:07:09Z (70-min slip /
thirteen missed 5-min ticks in a row) followed by 05:07:09Z →
05:27:58Z (20-min slip / four missed ticks), all three atlas
launchd processes healthy with PIDs 24233/81428/81432;
healthcheck-all self-resumed at 05:27:58Z (~23s AFTER this
diagnose was enqueued at 05:27:35Z) — no inline kickstart needed.
Thirty-sixth recurrence — this fired concurrently with the
baseball-bingo twin `3ea71a39` (same 05:27:35Z enqueue
timestamp), so the twin-fires-per-slip pattern still holds; both
projects share one cadence and every slip pings both diagnose
skills. Notable: back-to-back 70-min slips in the early-morning
Mini window are becoming the norm rather than the exception —
`events.py` live-probe gate is still un-landed.
2026-08-03 ~05:33Z (job `7a648d7b`, baseball-bingo answered `/healthz`
200 in 1.4ms and `/` 200 in 5.5ms on port 8790, `last_healthy_at` age
39s at diagnosis — already refreshed by the time the diagnose loaded;
same 03:57:12Z → 05:07:09Z 70-min slip / thirteen missed 5-min ticks
signature as the thirty-fifth/thirty-sixth recurrences immediately
above (queue-latency victim: enqueued 05:06:49Z, started 05:33:19Z
— 27 min queued behind the earlier diagnose burst), project PID
71682 healthy (launchd shows last exit `-15` from a prior SIGTERM,
not current). healthcheck-all had already self-resumed at 05:27:58Z
then 05:33:00Z before the diagnose ran — no inline kickstart needed.
Thirty-seventh recurrence — concurrent atlas twin `9fa3a72c` still
queued behind the earlier burst confirms twin-fires-per-slip. Notable:
queue-latency amplification is now a distinct failure mode of the
false-positive pattern — 5:06Z fire + 5:27Z fire = 4 stale diagnoses
in queue for one underlying slip. The `events.py` live-probe gate
spec at the bottom of this section would zero this out).
2026-08-03 ~05:27Z (job `bdc87c02`, atlas answered `/` 200 on port 8791,
`last_healthy_at` age at diagnosis fire was stale then refreshed to 3s old
after inline kickstart — `healthcheck.out.log` gap 05:07:09Z → 05:27:58Z
(21-min slip / four missed 5-min ticks in a row, still riding the tail of
the 70-min sleep-window slip that produced the thirty-fifth–thirty-seventh
recurrences overnight), all three atlas launchd processes healthy with
PIDs 24233/81428/81432. healthcheck-all kickstarted inline via
`gui/$(id -u)/com.assistant.healthcheck-all` and resumed at 05:37:55Z,
atlas `last_healthy_at` refreshed to 3s old. Thirty-eighth recurrence —
still atlas false positive; `events.py` live-probe gate spec below is
still un-landed and should be prioritized).
2026-08-03 ~06:43Z (job `bfbbaa74`, atlas answered `/` 200 in 74ms on
port 8791, `last_healthy_at` age at diagnosis fire was 35m stale,
refreshed to 2s after inline kickstart — `healthcheck.out.log` last
tick 06:08:09Z (seven missed 5-min ticks in a row: 06:13/18/23/28/33/38/43),
all three atlas launchd processes healthy with PIDs 24233/81428/81432
(same trio as recurrences 35–38, so the atlas main + dash-scheduler +
pm-edge have been continuously up through the whole slip streak).
`healthcheck-all` kickstarted inline via
`gui/$(id -u)/com.assistant.healthcheck-all` and resumed at 06:44:14Z,
both atlas and baseball-bingo `last_healthy_at` refreshed. Thirty-ninth
recurrence — same atlas false-positive shape; `events.py` live-probe
gate spec below still un-landed. Baseball-bingo appears not to have
tripped a diagnose fire this window despite the same DB staleness,
suggesting the 20-min threshold only crossed for one of them at eval time.
2026-08-03 ~06:44Z (job `5d2ec98b`, baseball-bingo — twin of the atlas
thirty-ninth just above; correcting that entry's assumption, baseball-bingo
DID fire a parallel diagnose in the same window, so this is a same-tick
twin-fire from the shared 06:08:09Z → 06:44:14Z healthcheck gap).
Baseball-bingo answered `/healthz` 200 in 9ms, `/` 200 with full HTML,
and `/static/style.css` 200 in 3ms on port 8790 — every code path healthy
including the FileResponse path that originally caught the July 30 startup
anyio ImportError. No kickstart needed — the natural 06:44:14Z tick had
already refreshed `last_healthy_at` to 8s old before the probe ran
(so the diagnose fired against a race window that was already closed by
the atlas-diagnose's inline kickstart one minute earlier). Historical note:
the six `TaskHandle`-from-anyio ImportError bursts in
`project.baseball-bingo.err.log` are ALL from the July 30 23:40 initial
startup (err.log unchanged since; process uptime 3d3h and stable);
`anyio 4.14.2` exports `TaskHandle` correctly at the current interpreter
state. Fortieth recurrence — still `events.py` live-probe gate un-landed;
also worth landing a same-tick dedup so parallel `atlas` + `baseball-bingo`
slips produce one diagnose fire, not two.

2026-08-03 ~09:42Z (job `daa80e8a`, baseball-bingo answered `/healthz`
200 in <1ms internal and 200 via the public tunnel `https://bingo.chrispiserchia.com/healthz`
with `{"status":"ok"}`. `last_healthy_at` age 33m58s at diagnosis —
`healthcheck.out.log` last tick 08:49:17Z → 09:25:51Z was a 36-min slip
(six missed 5-min ticks); the 09:25:51Z tick logged `checked=2 healthy=2`
but its psql UPDATE apparently did not land — DB still showed
09:09:21Z at diagnosis time, so this was actually a compound slip
(missed ticks AND a silent DB update loss on the 09:25 tick).
Project PID 71682 healthy with 3d6h uptime. Manually ran
`bash scripts/healthcheck-all.sh` inline to refresh — both
baseball-bingo and atlas `last_healthy_at` refreshed to <1s old at
09:43:37Z. Forty-first recurrence — `events.py` live-probe gate still
un-landed. New wrinkle: this occurrence adds *silent psql UPDATE loss*
on top of the usual missed-tick pattern; the healthcheck script uses
`psql ... > /dev/null 2>&1` and swallows any error, so a transient
DB blip or lock contention would go unnoticed. Consider surfacing
psql exit status in the summary line as a lightweight companion fix
alongside the events.py gate).

2026-08-03 ~09:42Z (job `3e813db1`, atlas twin of the baseball-bingo
diagnose `daa80e8a` immediately above — both diagnoses were dispatched
by the same event tick and share the exact 08:49:17Z → 09:25:51Z 36-min
healthcheck-all slip + silent psql UPDATE loss on the 09:25:51Z tick.
Atlas answered `/` 200 in 43ms on port 8791, `last_healthy_at` age was
33m20s at the 09:42:17Z fire, still stale on my first DB read at 09:42:41Z
(09:09:21Z stamp — confirming the 09:25:51Z tick's UPDATE never landed),
then refreshed to 34s old at 09:43:36Z when the natural launchd 09:43
tick finally ran successfully (no inline kickstart needed this time —
launchd caught up on its own). All three atlas launchd processes healthy
throughout with PIDs 24233/81428/81432, all state `running`. Forty-second
recurrence — this is the twin the baseball-bingo entry above hinted at
(same tick, same slip signature, same silent UPDATE loss). Notable: the
compound failure mode (missed ticks + silent UPDATE swallow) is now
observed twice back-to-back (41st and 42nd recurrences share it); the
lightweight companion fix — stop `psql ... > /dev/null 2>&1` in
`scripts/healthcheck-all.sh` and surface exit status in the summary —
is worth landing WITH the `events.py` live-probe gate.

2026-08-03 ~10:27Z (job `8b40c8d6`, atlas answered `/` 200 in 85ms on
port 8791, `last_healthy_at` age 21m15s at diagnosis — stamp 10:06:33Z
vs probe 10:27:48Z; `healthcheck.out.log` gap 10:06:33Z → 10:27:59Z
(21-min slip / four missed 5-min ticks in a row), all three atlas
launchd processes healthy with PIDs 24233/81428/81432 and state
`running`; `com.assistant.healthcheck-all` was NOT actively running
(PID `-`) so kickstarted inline via `gui/$(id -u)/com.assistant.healthcheck-all`
and cadence resumed at 10:27:59Z, atlas `last_healthy_at` refreshed to
7s old. Forty-third recurrence — atlas-only fire in the dispatch
window at diagnosis time; no concurrent baseball-bingo twin observed
for this slip. Notable: same missed-tick signature as most prior
recurrences, no silent-UPDATE-loss wrinkle this time. `events.py`
live-probe gate and `healthcheck-all.sh` psql-exit-status surfacing
both still un-landed.)

2026-08-03 ~14:29Z (job `9e0b1a78`, baseball-bingo answered `/healthz`
200 in 6.1ms and `/` 200 in 5.4ms with full HTML on port 8790,
`last_healthy_at` age 21m09s at diagnosis — stamp 14:08:27Z vs probe
14:29:36Z; `healthcheck.out.log` gap 13:47:17Z → 14:08:28Z (21-min slip
/ four missed 5-min ticks in a row), project PID 71682 healthy.
`com.assistant.healthcheck-all` was not actively running (PID `-`) so
kickstarted inline via `gui/$(id -u)/com.assistant.healthcheck-all`;
cadence resumed at 14:29:52Z, both baseball-bingo AND atlas
`last_healthy_at` refreshed to 7s old (one kickstart, both projects
refreshed — reinforcing the shared-cadence pattern). Forty-fourth
recurrence — baseball-bingo-only fire in the dispatch window at
diagnosis time; no concurrent atlas twin observed for this slip.
Notable: same missed-tick signature, no silent-UPDATE-loss wrinkle;
`events.py` live-probe gate and `healthcheck-all.sh` psql-exit-status
surfacing both still un-landed.)

2026-08-03 ~10:27Z (job `132fa29a`, baseball-bingo twin of atlas
job `8b40c8d6` immediately above — same 10:06:33Z → 10:27:59Z gap /
four missed 5-min ticks signature. baseball-bingo answered `/healthz`
200 in 5.8ms and `/` 200 in 4.7ms on port 8790, `last_healthy_at`
age 21m17s at diagnosis (stamp 10:06:33Z vs probe 10:27:47Z), project
PID 71682 healthy; healthcheck-all had already been kickstarted by
the concurrent atlas diagnose at 10:27:59Z so no second kickstart
needed, baseball-bingo `last_healthy_at` refreshed to 4s old.
Forty-fourth recurrence — the atlas entry above was written as
"atlas-only in the dispatch window" but this baseball-bingo twin
loaded moments later; twin-fires-per-slip pattern still holds. Same
false-positive signature; `events.py` live-probe gate still un-landed.)

2026-08-03 ~16:09Z (job `a66fc623`, baseball-bingo answered `/healthz`
200 in 6.2ms and `/` 200 in 6.7ms on port 8790, `last_healthy_at` age
34m11s at diagnosis — stamp 15:35:31Z vs probe 16:09:42Z;
`healthcheck.out.log` gap 15:35:32Z → 16:09:58Z (34-min slip / six
missed 5-min ticks in a row), project PID healthy.
`com.assistant.healthcheck-all` was `state = not running` (idle between
ticks — last exit 0) so kickstarted inline via
`gui/$(id -u)/com.assistant.healthcheck-all`; cadence resumed at
16:09:58Z, both baseball-bingo AND atlas `last_healthy_at` refreshed
to 7s old (shared-cadence pattern once again). Forty-fifth recurrence
— baseball-bingo-only fire in the dispatch window; no concurrent atlas
diagnose observed for this slip. Same missed-tick signature, no
silent-UPDATE-loss wrinkle; `events.py` live-probe gate and
`healthcheck-all.sh` psql-exit-status surfacing both STILL un-landed
after 45 recurrences.)

Also noticed while triaging: the atlas API log shows repeated
`invalid input syntax for type uuid: "AAPL"` errors from
`.next/server/app/api/atlas/{assets,candles}/route.js`. That's a real
pre-existing app bug (a stock ticker being passed where a UUID asset id
is expected) but it's unrelated to healthcheck — the root `/` route
still returns 200 and the launchd services stay up. Track separately if
still current after the next atlas deploy.

2026-08-03 ~11:28Z (job `440b02dd`, baseball-bingo — probed at
11:29:48Z, immediately after enqueue. `/healthz` 200 in 1.2ms and `/`
200 in 5.7ms on port 8790; port listener PID 71686 (child of the bash
launchd wrapper whose PID 71682 shows `LastExitStatus=15` — normal, the
python child outlives the shell). `last_healthy_at` at diagnosis was
11:29:05Z, i.e. 43s old — already fresh by the time this diagnose ran,
so the slip closed on its own between enqueue and pickup. Re-verified
`from anyio._core._tasks import TaskHandle` succeeds cleanly at the
current interpreter, confirming the June-30 `TaskHandle` ImportError
burst in `project.baseball-bingo.err.log` is stale and not the source of
this fire. Forty-fifth recurrence — same false-positive signature;
`events.py:_check_project_health` live-probe gate STILL un-landed.)

2026-08-03 ~11:28Z (job `fc3ab12d`, atlas twin of baseball-bingo job
`440b02dd` immediately above — same event tick (07:28:51 EDT / 11:28:51Z),
same slip signature. Atlas answered `/` 200 in 12ms on port 8791.
`last_healthy_at` at diagnosis was 11:29:05.883Z, 17s old at the first
DB read — the 11:29:06Z healthcheck-all tick had already fired
self-recovered before this diagnose job even picked up (no inline
kickstart needed). Preceding `healthcheck.out.log` gap 11:08:32Z →
11:29:06Z (20-min slip / four missed 5-min ticks). All three atlas
launchd processes healthy with PIDs 24233/81428/81432, state `running`.
Forty-sixth recurrence — twin-fires-per-slip pattern still holds
(45+46 = shared 11:08:32Z → 11:29:06Z slip). Same false-positive
signature; `events.py:_check_project_health` live-probe gate STILL
un-landed. Also re-observed the pre-existing atlas `invalid input
syntax for type uuid: "AAPL"` bug in `assets/candles` API route —
unrelated to healthcheck, root `/` still 200. No app-patch dispatched
from this session — diagnose-only lane.)

2026-08-03 ~11:53Z (job `db9c2625`, baseball-bingo — probed at
11:53:43Z. `/healthz` 200 in 4.0ms and `/` 200 in 4.5ms on port 8790,
project PID 71682 healthy. DB `last_healthy_at` was 2m54s old at
diagnosis (stamp 07:50:47 EDT / 11:50:48Z) — already refreshed by the
natural 11:50:48Z healthcheck-all tick before this diagnose loaded, no
inline kickstart needed. Preceding `healthcheck.out.log` slips this
session: 11:08:32Z → 11:29:06Z (20-min slip / four missed 5-min ticks)
then 11:29:06Z → 11:50:48Z (22-min slip / four missed ticks) — two
back-to-back slips in the same window, the second of which fired this
trigger. Forty-seventh recurrence — baseball-bingo-only fire in the
dispatch window at diagnosis time; no concurrent atlas diagnose observed
for this specific slip (jobs `440b02dd`+`fc3ab12d` were the twin for the
prior 11:08→11:29 slip). Same false-positive signature;
`events.py:_check_project_health` live-probe gate STILL un-landed.)

2026-08-03 ~11:50Z (job `b0efa36e`, baseball-bingo — probed at
11:55:37Z. `/healthz` 200 OK on port 8790, uvicorn PID 71686 (parent
71682) up since 2026-07-30, `state = running`. DB `last_healthy_at`
was 21m43s stale at diagnosis fire (07:50:31 EDT / 11:50:31Z; stamp
was 07:29:06 EDT / 11:29:06Z) — refreshed to 58s old by the natural
11:50:48Z healthcheck-all tick which landed 17s AFTER this diagnose
was enqueued, no inline kickstart needed. `healthcheck.out.log` gap
11:29:06Z → 11:50:48Z (21m42s slip / four missed 5-min ticks); a
fresh 11:55:49Z tick has since fired on cadence. Historical anyio
`TaskHandle` ImportError in `project.baseball-bingo.err.log` last
written Jul 30 23:40 — the read_project_logs stderr dump surfaces
these ancient errors on every diagnose and is misleading; they are
pre-restart PID 3619 and no longer relevant (verified: anyio 4.14.2
in shared venv now exports `TaskHandle` from `_core._tasks`). Forty-eighth
recurrence — baseball-bingo-only fire in the dispatch window at
diagnosis time; no concurrent atlas diagnose queued for this specific
slip. Same false-positive signature; `events.py:_check_project_health`
live-probe gate STILL un-landed after 48 recurrences.)

2026-08-03 ~11:50Z (job `69cb8760`, atlas twin of baseball-bingo job
`b0efa36e` immediately above — same event tick (07:50:31 EDT /
11:50:31Z), same 11:29:06Z → 11:50:48Z slip. Atlas answered `/` 200
in 65ms on port 8791. DB `last_healthy_at` was 3m25s old at diagnosis
(stamp 07:50:47 EDT / 11:50:47Z) — already refreshed by the natural
11:50:48Z healthcheck-all tick which landed 17s AFTER the event
trigger fired, no inline kickstart needed. atlas launchd PIDs
24233/81428/81432 healthy, `state = running`; the `-15` last-exit
codes visible in `launchctl list` are STALE from prior instances and
misleading. This session also observed and cancelled a queued
duplicate atlas diagnose `30bbf10e` stacked behind this running peer
— dedup race: `_should_trigger_project_diagnose` filters
`existing_diagnoses` on `Job.resolved_skill == 'self-diagnose'`, but
queued-but-unresolved duplicates have NULL `resolved_skill` and slip
through, so during back-to-back slips the trigger double-fires per
project. Folded into the server-patch spec below. Re-observed the
pre-existing atlas `invalid input syntax for type uuid: "AAPL"` bug
in `.next/server/app/api/atlas/{assets,candles}/route.js` — unrelated
to this class, root `/` still 200, not addressed here. Forty-ninth
recurrence.

**NEW — prevention patch dispatched**: server-patch job
`5dfebb42-5e0f-4009-be11-1112b9d4b9b2` enqueued at 11:54Z to land
BOTH the live-probe gate in `events.py:_check_project_health` AND
the queued-but-unresolved dedup fix. First landing attempt after 48
diagnose-only fires. If it merges green, this class of false
positive should end; if it fails or gets deferred, the recurrence
counter will keep climbing and the next self-diagnose should
re-dispatch.)

2026-08-03 ~12:41Z (job `61e9de7d`, baseball-bingo — probed at 12:41:38Z.
`/healthz` 200 in 17ms and `/` 200 in 6ms on port 8790, uvicorn PID 71686
(parent 71682) up since 2026-07-30, `state = running`. DB `last_healthy_at`
was 20m38s stale at diagnosis fire (stamp 08:21:00 EDT / 12:21:00Z) —
refreshed to fresh by the natural 12:41:41Z healthcheck-all tick that
landed 3s after this diagnose picked up, no inline kickstart needed.
`healthcheck.out.log` gap 12:21:07Z → 12:41:41Z (20m34s slip / four
missed 5-min ticks). Concurrent atlas twin `7a19aaf7` running in same
dispatch window (both enqueued at 12:41:04Z, same event tick — the
queued-but-unresolved dedup race still holds since the prevention patch
never landed). **Critical finding**: prior server-patch `5dfebb42` from
`~11:54Z` completed but the fix was **never committed or pushed**. The
session made the edits to `src/runner/events.py` (`_check_project_health`
+ `_resolve_probe_decision` helper) AND added 6 passing tests to
`tests/test_pure_functions.py`, but the workspace `workspace_synced` event
records only `canonical fast-forwarded from origin` (i.e. no local commits
to push). The session ended after the test run without a git commit,
git push, TASK_COMPLETE marker, or code_review invocation. `git log
origin/main -- src/runner/events.py` still shows `197f239` (pre-patch) as
the latest touch — the changes were thrown away when the workspace was
GC'd. Also noted: guard hook mis-fired on a benign `find` command
containing the protected-path substring — separate secondary bug worth
tightening. Fiftieth recurrence — same false-positive signature; live-probe
gate STILL un-landed. Re-dispatching a fresh server-patch with explicit
COMMIT-AND-PUSH-BEFORE-EXIT instructions.)

**Fifty occurrences** across atlas and baseball-bingo. Server-patch
`5dfebb42` dispatched 2026-08-03 11:54Z made the edits + tests but
**never committed** (see 50th entry above); re-dispatched fresh
`server-patch` at 2026-08-03 12:44Z with explicit commit/push
requirements + INV-13 code-review gate reminder.

2026-08-03 ~14:29Z (job `b3b68a9e`, atlas — probed at 14:29:39Z.
`/` 200 in 63ms on port 8791, all three atlas launchd processes healthy
(PIDs 24233 / 81428 / 81432, `state = running`; the `-15` LastExitStatus
on the two sub-services is STALE from a prior restart cycle, not a
live crash). `last_healthy_at` at diagnosis fire was 21m11s stale
(stamp 14:08:27Z vs current 14:29:39Z); refreshed to 39s old by the
14:29:52Z healthcheck-all tick that fired 13s AFTER this diagnose
picked up, no inline kickstart needed. Preceding `healthcheck.out.log`
gap 13:47:17Z → 14:08:28Z (21m11s slip / four missed 5-min ticks)
followed by 14:08:28Z → 14:29:52Z (21m24s slip / four missed 5-min
ticks) — two back-to-back slips, the second of which fired this
trigger. Same macOS-sleep-cadence-slip signature as recurrences 43–50.
Concurrent baseball-bingo twin `9e0b1a78` running in same dispatch
window (both enqueued at 14:29:11Z, same event tick — the
queued-but-unresolved dedup race still holds).

**Fifty-first recurrence. CRITICAL META-FINDING**: the second
server-patch `2bfb6d20` dispatched 2026-08-03 12:44Z (08:44 EDT) DID
commit locally as `4330b2f` (+415/-5, 13 new tests, all 61 event
tests green, code-review agent invoked) — but the workspace was
never pushed to origin before job completion. Same PATTERN as prior
patch `5dfebb42` (which never committed at all), same OUTCOME
(fix not on origin/main). `workspace_synced` event on this job reads
`"canonical fast-forwarded from origin"` — the runtime canonical
pulled what origin already had, but the workspace's local `4330b2f`
was garbage-collected with the workspace directory. Verified: `git
cat-file -e 4330b2f` in the runtime clone reports "malformed object
name"; commit is gone. Two consecutive server-patch attempts have
failed to actually land the same fix.

**Root cause of the meta-bug is NOT in this skill's lane** — it's in
`src/runner/workspaces.py` (or the session-finalization hook that's
supposed to `git push` workspace commits before ff-syncing the
canonical). This is a **medium-risk server-code bug** that requires a
`server-patch` to `src/runner/workspaces.py` and the session teardown
path. Diagnose-only from this session — NOT re-dispatching a third
server-patch for the events.py fix until the workspace-push bug is
addressed, since it would land in the same trap.

No inline action taken on atlas — it's healthy, the false-positive
class continues to fire, and dispatching more one-off server-patches
just burns cycles without landing the fix. Owner action needed:
investigate why `src/runner/workspaces.py` isn't pushing workspace
commits back to origin after session completion, then re-dispatch
the events.py live-probe gate (spec still valid, unchanged).)

2026-08-03 ~16:09Z (job `5e0d207e`, atlas — probed at 16:09:37Z.
`/` returned HTTP 200 in 58ms on port 8791. All three atlas launchd
processes healthy: `com.assistant.project.atlas` PID 24233 (uptime
2d 21h), `atlas-dash-scheduler` PID 81428 (uptime 3d 11h),
`atlas-pm-edge` PID 81432 (uptime 3d 11h); the `-15` LastExitStatus on
each launchctl row is stale from a prior restart cycle, not a live
crash. `last_healthy_at` at diagnosis fire was 34m26s stale (stamp
15:35:32Z vs current 16:09:37Z); refreshed to 19s old by the natural
16:09:58Z healthcheck-all tick that fired ~20s AFTER this diagnose
picked up, so no inline kickstart needed. `healthcheck.out.log` gap
15:35:32Z → 16:09:58Z (34m26s slip / **six** missed 5-min ticks — the
longest slip in the current recurrence run). Concurrent baseball-bingo
row also fresh (staleness 19.7s), so twin was NOT dispatched this tick
(single-fire this time — the queued-but-unresolved dedup race just
happened not to race). Same macOS-sleep-cadence-slip signature as
recurrences 43–51.

**Fifty-second recurrence.** Per the 51st entry above, NOT
re-dispatching a third server-patch for the `events.py` live-probe gate:
two prior server-patches (`5dfebb42` never committed, `2bfb6d20`
committed as `4330b2f` but the workspace commit was garbage-collected
before push) have proven that the workspace-push meta-bug in
`src/runner/workspaces.py` traps any fix landed via the normal
`server-patch` lane. Verified this session: `git log origin/main --
src/runner/events.py` still shows `197f239` as the latest touch (fix
never landed on origin/main). Until the workspace-push bug is fixed,
re-dispatching this patch just repeats the same trap. No inline action
taken on atlas — it's healthy; healthcheck-all self-resumed 21s after
the diagnose fired, and the false-positive class continues to fire on
its own cadence-slip signature.)

2026-08-03 ~17:02Z (job `01a572fd`, atlas — probed at 17:02:02Z.
`/` returned HTTP 200 on port 8791. All three atlas launchd processes
healthy: `com.assistant.project.atlas` PID 24233 (uptime 2d 21h 54m),
`atlas-dash-scheduler` PID 81428 (uptime 3d 12h 32m), `atlas-pm-edge`
PID 81432 (uptime 3d 12h 32m); the `-15` LastExitStatus on each
launchctl row is stale from a prior restart cycle, not a live crash.
`last_healthy_at` at diagnosis fire was 27m15s stale (stamp 16:35:14Z
vs current 17:02:02Z); refreshed to 11s old by the natural 17:02:29Z
healthcheck-all tick that fired ~27s AFTER this diagnose picked up,
so no inline kickstart needed. `healthcheck.out.log` gap 16:35:14Z →
17:02:29Z (27m15s slip / **five** missed 5-min ticks), preceded by a
normal-cadence run 16:09:58Z → 16:15:00 → 16:20:01 → 16:25:02 →
16:30:11 → 16:35:14, then the slip. Concurrent baseball-bingo row also
fresh (staleness ~11s), so twin was NOT dispatched (single-fire this
tick). Same macOS-sleep-cadence-slip signature as recurrences 43–52.

**Fifty-third recurrence.** Per the 51st entry above, still NOT
re-dispatching a third `server-patch` for the `events.py` live-probe
gate: the workspace-push meta-bug in `src/runner/workspaces.py` /
session-finalization continues to trap the fix in the runtime clone
before it reaches origin. Verified this session: last commit touching
`src/runner/events.py` on origin/main is still `197f239` (pre-patch).
Owner action still needed on the workspace-push meta-bug before the
events.py fix can land through the normal patch lane. No inline action
taken on atlas — it's healthy; healthcheck-all self-resumed 27s after
this diagnose picked up. Cadence has since returned to normal 5-min
ticks (confirmed by post-fire tick at 17:02:29Z).)

2026-08-03 ~17:01Z (job `ba818f6f`, baseball-bingo — the concurrent
twin of atlas job `01a572fd` immediately above. Both were enqueued at
13:01:33.22–13:01:33.24 EDT (17:01:33Z), before the natural 17:02:29Z
healthcheck-all tick refreshed either project's `last_healthy_at`.
The atlas session (which ran first) mis-reported this fire as a
"single-fire this tick" — it wasn't; the baseball-bingo twin was
already enqueued, just picked up ~26 min later on the runner queue.
baseball-bingo verified healthy at 17:02+: `/healthz` returned
`{"status":"ok"}` (HTTP 200) on port 8790; PID 71682 uvicorn process
uptime 3d 13h 23m, out.log shows continuous 200s throughout the
"stale" window (many `GET /healthz HTTP/1.1 200 OK` entries).
`last_healthy_at` refreshed by the 17:02:29Z natural tick to ~38s
old by the time this session probed, so no inline kickstart needed.
Same macOS-sleep-cadence-slip signature (16:35:14Z → 17:02:29Z, five
missed 5-min ticks). No inline action taken — project is healthy,
events.py live-probe gate remains un-landed pending the workspace-push
meta-bug fix. Fifty-fourth recurrence; twin-fires-per-slip pattern
still holds (the atlas entry's "single-fire" note above is corrected
by this entry).

2026-08-03 ~17:53Z (job `9ae1fd83`, baseball-bingo answered `/healthz`
200 in 1.5ms and `/` 200 in 7.1ms on port 8790, `last_healthy_at` age
20m38s at trigger fire — refreshed to 13s old by the time the direct
probe ran; `healthcheck.out.log` gap 17:32:48Z → 17:53:23Z (20-min
slip past the 5-min cadence, i.e. four missed 5-min ticks in a row),
project PID 71682 up 3d14h stable; healthcheck-all had already
self-resumed at 17:53:23Z before diagnosis ran — no inline kickstart
needed. Historical anyio `TaskHandle` ImportError bursts in
`project.baseball-bingo.err.log` are still from the July 30 23:40
initial startup (err.log unchanged since; process uptime 3d14h and
stable); anyio exports `TaskHandle` correctly at the current
interpreter state. Fifty-fifth recurrence — baseball-bingo-only fire
in the dispatch window at diagnosis time; no concurrent atlas twin
observed for this slip. `events.py` live-probe gate STILL un-landed.

2026-08-03 ~17:54Z (job `83096a78`, atlas twin of baseball-bingo
`9ae1fd83` immediately above — same 17:32:48Z → 17:53:23Z 20-min slip
/ four missed 5-min ticks signature. Atlas answered `/` 200 in 34ms
on port 8791, `last_healthy_at` age 10s at diagnosis — already
refreshed to fresh by the 17:53:23Z self-resumed tick before this
diagnose loaded. All three atlas launchd processes healthy with PIDs
24233/81428/81432, state `running` (the `-15` LastExitStatus entries
are stale from prior restart cycles, not live crashes).
healthcheck-all self-resumed at 17:53:23Z before diagnosis ran — no
inline kickstart needed. Fifty-sixth recurrence — corrects the
baseball-bingo 55th entry's "no concurrent atlas twin observed" note;
twin-fires-per-slip pattern still holds. Same false-positive signature;
per recurrences 51–54, still NOT re-dispatching a third server-patch for
the `events.py` live-probe gate — the workspace-push meta-bug in
`src/runner/workspaces.py` continues to trap the fix in the runtime
clone before it reaches origin (last touch of `src/runner/events.py`
on origin/main is still `197f239`, pre-patch). Owner action still
needed on the workspace-push meta-bug before the events.py fix can
land through the normal patch lane.)

2026-08-03 ~18:24Z (job `fa287ee8`, atlas — probed at 18:24:16Z.
`/` returned HTTP 200 in 30ms on port 8791. All three atlas launchd
processes healthy with PIDs 24233 / 81428 / 81432, state `running`
(the `-15` LastExitStatus entries are stale from prior restart cycles,
not live crashes). `last_healthy_at` at diagnosis fire was ~20m49s
stale (stamp 18:03:27Z vs probe 18:24:16Z); refreshed to fresh by the
18:24:06Z natural healthcheck-all tick that fired ~10s BEFORE the
direct probe ran — no inline kickstart needed. `healthcheck.out.log`
gap 18:03:27Z → 18:24:06Z (20m39s slip / four missed 5-min ticks),
preceded by 17:53:23Z → 17:58:26Z → 18:03:27Z on normal cadence and
followed immediately by the recovery tick. Same macOS-sleep-cadence-slip
signature as recurrences 43–56. Fifty-seventh recurrence. Per the
51st entry, still NOT re-dispatching a third `server-patch` for the
`events.py` live-probe gate — the workspace-push meta-bug in
`src/runner/workspaces.py` / session-finalization continues to trap
the fix in the runtime clone before it reaches origin (verified: last
touch of `src/runner/events.py` on origin/main is still `197f239`,
pre-patch). Owner action still needed on the workspace-push meta-bug
before the events.py fix can land through the normal patch lane. No
inline action taken on atlas — it's healthy; the pre-existing
`invalid input syntax for type uuid: "AAPL"` bug in
`.next/server/app/api/atlas/{assets,candles}/route.js` is still
present in stderr but unrelated to healthcheck and root `/` still
serves 200.)

2026-08-03 ~19:41Z (job `c057fea4`, baseball-bingo twin of atlas job
`2c663dd3` — both enqueued at 19:40:37Z, 13ms apart, but this
baseball-bingo diagnose reported in AFTER the atlas twin had already
kickstarted `healthcheck-all` at 19:41:16Z. At probe time
(19:41:09Z curl), baseball-bingo answered `/healthz` 200 and root `/` 200
on port 8790, PID 71682 (uvicorn started 3d16h ago, stable). Manual
`healthcheck-all` invocation refreshed `last_healthy_at` to
2026-08-03 19:42:00Z (~14s stale at check), then the natural 19:41:16Z
tick — from the atlas twin's kickstart — was already recorded in
`healthcheck.out.log`. Six historical anyio `TaskHandle` ImportError
bursts in `project.baseball-bingo.err.log` are still all from the July
30 23:40 initial partial pip-install (pre-restart PID 3619) and no
longer relevant (verified: `from anyio._core._tasks import TaskHandle`
succeeds cleanly at anyio 4.14.2 in shared venv). Fifty-ninth
recurrence — dispatch-window twin of the atlas 58th entry immediately
above; no additional kickstart needed since the atlas twin had already
resumed cadence 7s before this job's probe. Same
macOS-sleep-cadence-slip signature as recurrences 43–58. Per the 51st
entry, still NOT re-dispatching a third `server-patch` for the
`events.py` live-probe gate — the workspace-push meta-bug in
`src/runner/workspaces.py` / session-finalization continues to trap the
fix in the runtime clone before it reaches origin. Owner action on
the workspace-push meta-bug remains the true unblock for the events.py
live-probe fix that would zero these false positives.)

2026-08-03 ~19:40Z (job `2c663dd3`, atlas twin of baseball-bingo job
`c057fea4` — both enqueued at 19:40:37Z, 13ms apart. Atlas answered `/`
200 in 60ms on port 8791 at diagnosis. All three atlas launchd
processes healthy with PIDs 24233 / 81428 / 81432, state `running` (the
`-15` LastExitStatus entries are stale). `last_healthy_at` at diagnosis
was 21m19s stale (stamp 19:19:46Z vs probe 19:40:56Z). `healthcheck-all`
had no PID — cadence had stopped. `healthcheck.out.log` gap
19:19:46Z → 19:41:16Z (21m30s / four missed 5-min ticks); inline
`launchctl kickstart -k gui/$UID/com.assistant.healthcheck-all`
resumed cadence at 19:41:16Z, both atlas and baseball-bingo
`last_healthy_at` refreshed to ~7s old. Fifty-eighth recurrence — same
macOS-sleep-cadence-slip signature as recurrences 43–57. Per the 51st
entry, still NOT re-dispatching a third `server-patch` for the
`events.py` live-probe gate — the workspace-push meta-bug in
`src/runner/workspaces.py` / session-finalization continues to trap the
fix in the runtime clone before it reaches origin (last touch of
`src/runner/events.py` on origin/main is still `197f239`, pre-patch).
Owner action still needed on the workspace-push meta-bug before the
events.py fix can land through the normal patch lane. No inline action
taken on atlas — it's healthy; the pre-existing
`invalid input syntax for type uuid: "AAPL"` bug in
`.next/server/app/api/atlas/{assets,candles}/route.js` is unrelated
to healthcheck and root `/` still serves 200.)

**Concrete server-patch spec** (`src/runner/events.py:300` `_check_project_health`):
insert a live-probe gate before `enqueue_job`. Between lines 323-330,
for each `slug` returned by `_should_trigger_project_diagnose`, fetch
the project's `port` and issue `curl -sf -m 3 http://localhost:<port><healthcheck_path>`
(or an async httpx GET). If it returns 200, skip the enqueue and just
refresh `last_healthy_at` inline (or leave for the next healthcheck-all
tick). Only enqueue diagnose when the live probe also fails. This
converts the 28+ false positives to zero without changing the trigger
semantics for genuine outages. Cost: one HTTP call per slug per tick
(negligible; already happens in healthcheck-all)._

2026-08-03 ~21:48Z (job `aaa710c0`, atlas-only fire — no concurrent
baseball-bingo twin observed this slip despite both sharing the same
cadence, and no baseball-bingo self-diagnose in the last 2h in the DB;
possible race in the events loop tick, unimportant since both projects
were healthy). Atlas answered `/` HTTP 200 on port 8791; all three
launchd processes healthy with PIDs 24233 / 81428 / 81432 (main web
uptime 3d02h, sub-services 3d17h — stable). `last_healthy_at` at
diagnosis was 20m20s stale (stamp 21:27:54Z vs trigger evaluation
21:48:14Z — dead-on the 20-min threshold). `healthcheck.out.log` gap
21:27:54Z → 21:48:15Z (20m21s / four missed 5-min ticks). By the time
the diagnose skill loaded and probed (~21:53Z), `healthcheck-all` had
already self-resumed at 21:48:15Z and again at 21:53:16Z — no inline
kickstart needed. Sixtieth recurrence — same macOS-sleep-cadence-slip
signature as recurrences 43–59. Per the 51st entry, still NOT
re-dispatching a `server-patch` for the `events.py` live-probe gate —
the workspace-push meta-bug documented above continues to trap the
fix in the runtime clone before it reaches origin. Owner action on
the workspace-push meta-bug remains the true unblock for the
events.py live-probe fix that would zero these false positives.
Prior healthcheck.out.log gaps in the same session (20:26:29Z →
21:02:47Z = 36m, and 21:27:54Z → 21:48:15Z = 20m) confirm the
cadence-slip pattern is still active on this Mini.)

2026-08-03 ~22:23Z (job `348ec5db`, atlas-only fire — no concurrent
baseball-bingo twin observed this slip). Atlas answered `/` HTTP 200
in 64ms on port 8791; all three launchd processes healthy with PIDs
24233 / 81428 / 81432. `last_healthy_at` stamp 22:03:19Z vs diagnosis
probe 22:23:50Z (20m31s stale — dead-on the 20-min threshold).
`healthcheck.out.log` gap 22:03:19Z → 22:24:01Z (20m42s / four
missed 5-min ticks) — cadence had paused. Ticked inline via
`launchctl kickstart -k gui/$(id -u)/com.assistant.healthcheck-all`;
`last_healthy_at` refreshed to <1s at 22:24:00Z. Sixty-first
recurrence — same macOS-sleep-cadence-slip signature as 43–60. Per
the 51st entry, still NOT re-dispatching a third `server-patch` for
the `events.py` live-probe gate; the workspace-push meta-bug in
`src/runner/workspaces.py` / session-finalization continues to trap
the fix in the runtime clone before it reaches origin (last touch of
`src/runner/events.py` on origin/main is still `197f239`, pre-patch).
Owner action still needed on the workspace-push meta-bug before the
events.py fix can land through the normal patch lane.)

2026-08-03 ~23:49Z (job `24bb4633`, baseball-bingo-only fire — no
concurrent atlas twin observed at diagnosis time). Baseball-bingo
answered `/healthz` HTTP 200 in 11ms and `/` HTTP 200 in 5.5ms on port
8790; project PID 71682 up 3d20h without restart. `last_healthy_at`
stamp 23:14:18Z vs diagnosis probe ~23:49:35Z (35m17s stale — seven
missed 5-min ticks past the 20-min threshold). `healthcheck.out.log`
gap 23:14:18Z → 23:49:46Z (35m28s). Kickstarted inline via
`launchctl kickstart -k gui/$(id -u)/com.assistant.healthcheck-all`;
next tick landed at 23:49:46Z, `last_healthy_at` refreshed.
Sixty-second recurrence — same macOS-sleep-cadence-slip signature as
43–61. Per the 51st entry, still NOT re-dispatching a third
`server-patch` for the `events.py` live-probe gate; workspace-push
meta-bug continues to trap that fix in the runtime clone. Owner
action on the workspace-push meta-bug remains the true unblock.)

2026-08-03 ~23:49Z (job `d8cbf7aa`, atlas twin of the baseball-bingo
diagnose immediately above — both fired for the same 35m28s cadence
slip). Atlas answered `/` HTTP 200 in 110ms on port 8791; all three
launchd processes healthy (main PID 64303, dash-scheduler 62602,
pm-edge 62600). `last_healthy_at` stamp 23:14:18Z vs diagnosis probe
23:49:33Z (35m15s stale, seven missed 5-min ticks past the 20-min
threshold). `healthcheck.out.log` gap 23:14:18Z → 23:49:46Z
(35m28s). pmset log confirms Mini entered Maintenance Sleep at
2026-08-03 19:33:05 -0400 (23:33:05Z) and DarkWoke at 19:48:39 -0400
(23:48:39Z) — the sleep window overlaps the missed ticks. No inline
kickstart needed: the concurrent baseball-bingo twin (`24bb4633`)
had already kickstarted healthcheck-all, and this diagnose's own
manual `bash scripts/healthcheck-all.sh` invocation ticked in the
same 23:49:44-46Z window (atlas last_healthy_at refreshed to <5s).
Sixty-third recurrence — twin-fires-per-slip pattern continues; per
the 51st entry, still NOT re-dispatching a third `server-patch` for
the `events.py` live-probe gate; workspace-push meta-bug continues
to trap that fix in the runtime clone. Owner action on the
workspace-push meta-bug remains the true unblock.)

## Symptom: `atlas-daily-brief` fails with `error_max_turns: Reached maximum number of turns (14)` after `atlas-dash packet` errors

### Diagnostic
```bash
cd "$HOME/Library/Application Support/ai-server/projects/atlas"
set -a; source .env; set +a
dashboard/.venv/bin/atlas-dash packet
# → decimal.InvalidOperation from holdings.py:153 (portfolio_summary)
```

Audit log signature (see e.g. `ba92d4d4-08c5-4163-a1f2-b1a1768c4e35.jsonl`):
step 1's `atlas-dash chat-context --market` succeeds, step 1's `atlas-dash packet`
returns exit 1, then the session spends its remaining turns probing the atlas DB
schema (`\d holdings`, `\d portfolio_snapshots`, `\d assets`, …) trying to
reconstruct the packet by hand — hits `max_turns: 14` before authoring the brief.

### Root cause
Two things compound:
1. **`atlas-dash packet` bug** — `dashboard/atlas_dash/holdings.py:153` (and :157)
   does `val / total_value * Decimal("100")` guarded only by `total_value > 0`. A
   non-finite Decimal (NaN) in one asset class total sneaks past that guard and
   trips `decimal.InvalidOperation`. Live snapshot shows `total_value≈$156k`, so
   it's not zero — it's NaN or precision overflow in one of the per-class sums.
2. **Skill has no degraded path** — `skills/atlas-daily-brief/SKILL.md` treats
   `atlas-dash packet` as required. When it fails the model reasonably tries to
   reconstruct book state from raw SQL, but the 14-turn budget is sized for the
   happy path (3 gathers → author → save → summary).

### Fix
- Real fix: patch atlas in the dev clone (`~/Documents/repos/atlas`) — filter
  non-finite Decimals from `priced` in `portfolio_summary()` (and add `.is_finite()`
  alongside `> 0` guards at `holdings.py:88, 153, 157`). Deploy via
  `/task redeploy atlas`. Dispatched as app-patch job on 2026-08-04.
- Skill hardening (follow-up): teach `atlas-daily-brief` to degrade gracefully
  when `packet` fails — read `portfolio_snapshots` (schema:
  `ts, total_value, total_cost, source`) for yesterday's totals and mark the
  brief's Book line as "(fallback from snapshot, packet failed)". Prevents
  every future packet regression from silently killing the pre-open read.

### Prevention
Any atlas CLI subcommand the daily-brief skill depends on should have a
graceful-fallback branch in the skill AND a golden test in the dashboard
package. NaN/inf Decimals are a recurring hazard for finance code — filter
them at the boundary (`valued_holdings`) rather than defending every consumer.

## Adding entries to this file

When you hit a new failure, append a section here in this shape:

```markdown
## Symptom: <what the user sees>

### Diagnostic
<exact commands to run>

### Root cause
<what's actually happening>

### Fix
<exact commands>

### Prevention
<if applicable — what to change in skill/code/config to stop the class of issue>
```

This is exactly the GOTCHAS.md pattern but for system-level failures. If the
issue is scoped to one module, append to that module's `.context/modules/<x>/skills/GOTCHAS.md`
instead.
