# TROUBLESHOOTING

Common failure modes and exact debug steps. Add to this as you encounter new
failures in the wild — it's a living document.

> **How this doc is organized**: by failure *symptom*, because that's what you
> have when something breaks. Each symptom maps to one or more root causes with
> specific diagnostics.

---

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

**Thirty-eight+ occurrences** across atlas and baseball-bingo without
the prevention patch being landed — the `events.py` guard should be
top of the queue.

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
