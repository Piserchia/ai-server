# TROUBLESHOOTING

Common failure modes and exact debug steps. Add to this as you encounter new
failures in the wild — it's a living document.

> **How this doc is organized**: by failure *symptom*, because that's what you
> have when something breaks. Each symptom maps to one or more root causes with
> specific diagnostics.

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
