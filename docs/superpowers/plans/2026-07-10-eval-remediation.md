# Eval Remediation (2026-07-10) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the four silent plumbing defects found in `docs/EVALUATION_2026-07-10.md` (post-review/escalation never fire; review.py broken; stranded queued jobs starving the self-improvement loop; dead backups), make the atlas skill family actually dispatch as skills, and execute the repo/docs cleanup batch.

**Architecture:** No new subsystems. Small surgical fixes in `src/runner/` (main, review, session, reconcile, router), one skill-body update (server-upkeep), config-level model tiers, and documentation/repo hygiene. Every fix gets either a pure-function test (house style) or an explicit runbook verification.

**Tech Stack:** Python 3.12, SQLAlchemy async, Redis, Claude Agent SDK, pytest, bash/launchd.

## Global Constraints

- Never set `ANTHROPIC_API_KEY` anywhere (subscription auth only).
- `src/`, `scripts/`, `alembic/` changes ship via a `server-patch`-style PR — manual merge only (INV-4). **Note:** the automated code-review gate is itself broken until T4+T5 merge; review the Wave-1 PR interactively (`/code-review` or human).
- Skills (`skills/*/SKILL.md`) and docs may be committed directly per repo policy.
- Never commit or write tracked files inside `projects/atlas` (single-writer rule; atlas changes go to the dev repo `~/Documents/repos/atlas` and deploy via `atlas-redeploy`).
- Every module touched gets a `.context/modules/<x>/CHANGELOG.md` entry (pre-commit hook enforces for `src/`).
- Global default model stays `claude-sonnet-4-6`.
- Run `SERVER_ROOT=$(pwd) pipenv run pytest -q` (expect 560+ passing) and `pipenv run python scripts/lint_docs.py` before each commit.

**Execution order:** T1 → T2 → T3 (P0, human/god) · then one PR for Wave 1 in this order: T8, T4, T5, T6, T7, T9 · T10 (skill commit) · then T11 (atlas dev repo) · T12–T15 · T16–T17 backlog.

---

### Task T1: Unstrand the two phantom `queued` jobs (P0 — human or god session)

**Files:** none (DB + audit log only)

**Why now:** these two rows make `_check_idle_queue_review` see a busy queue forever; `review-and-improve` cannot fire until they reach a terminal state. Both are schedule-generated and will recur on their own cadence, so **fail** them (don't re-run last night's upkeep at 6 PM).

- [ ] **Step 1: Confirm they are still stranded**

```bash
redis-cli lrange jobs:queue 0 -1   # expect: empty
DSN=$(awk -F= '/^POSTGRES_DSN=/ {print $2}' .env | sed 's/+asyncpg//')
psql "$DSN" -c "SELECT id, kind, created_at FROM jobs WHERE status='queued';"
# expect exactly: bd5ecf66-… (server-upkeep) and 0ef2955c-… (atlas-daily-brief)
```

- [ ] **Step 2: Write terminal audit events (keeps INV-2 true) + index**

```bash
PYTHONPATH=. pipenv run python3 - <<'EOF'
from src import audit_log
from src.config import settings
from src.runner.audit_index import append_to_index
for jid in ("bd5ecf66-7884-4f3f-899f-e4f03be39c4c",
            "0ef2955c-565b-4c99-91bf-1d31ad81f409"):
    audit_log.append(jid, "job_failed",
                     error="stranded: queued row with no Redis queue entry",
                     error_category="stranded")
    append_to_index(settings.audit_log_dir, jid)
print("done")
EOF
```

- [ ] **Step 3: Fail the rows**

```bash
psql "$DSN" -c "UPDATE jobs SET status='failed',
  error_message='stranded: queued row with no Redis queue entry (EVALUATION_2026-07-10 §3.5)',
  completed_at=now()
  WHERE status='queued'
  AND id IN ('bd5ecf66-7884-4f3f-899f-e4f03be39c4c','0ef2955c-565b-4c99-91bf-1d31ad81f409');"
```

- [ ] **Step 4: Verify the self-improvement loop wakes up**

Within ~2 minutes the event loop should enqueue the idle-queue retrospective:

```bash
sleep 120 && psql "$DSN" -c "SELECT kind, status, created_at FROM jobs WHERE kind='review-and-improve' ORDER BY created_at DESC LIMIT 1;"
# expect: one row, created just now
```

Expected side effect: its first run may propose fixes that overlap this plan — that's fine; proposals are deduped by the proposals table.

---

### Task T2: Fix backups + untrack the committed tarball (P0)

**Files:**
- Modify: `scripts/backup.sh` (top of file)
- Modify: `.gitignore`
- Update: `.context/modules/hosting/CHANGELOG.md`

- [ ] **Step 1: Give launchd a PATH that contains pg_dump**

Insert directly after the `set -euo pipefail` line of `scripts/backup.sh`:

```bash
# launchd provides a minimal PATH; Homebrew tools (pg_dump, tar helpers, rclone)
# live outside it. Explicit PATH so the 04:00 timer works (exit-127 incident,
# broken since 2026-04; see EVALUATION_2026-07-10 §3.7).
export PATH="/opt/homebrew/opt/postgresql@15/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
```

- [ ] **Step 2: Run it now and verify**

```bash
launchctl kickstart gui/$(id -u)/com.assistant.backup
sleep 30 && ls -la volumes/backups/ && tail -3 volumes/logs/backup.err.log
```
Expected: a `backup-2026-07-10.tar.gz` exists; no new `command not found` lines.

- [ ] **Step 3: Untrack runtime artifacts**

```bash
git rm --cached volumes/backups/backup-2026-04-17.tar.gz
# .gitignore: replace the narrow `volumes/jobs.db` entry with:
#   volumes/
rm -f volumes/jobs.db   # 0-byte mystery file; no writer in src/. If it returns, an SDK session makes it — grep audit logs then.
```

- [ ] **Step 4: CHANGELOG (hosting) + commit**

```bash
git add scripts/backup.sh .gitignore .context/modules/hosting/CHANGELOG.md
git commit -m "fix(backup): launchd PATH for pg_dump; stop tracking volumes/ artifacts"
```

---

### Task T3: Finish the R2 + heartbeat-worker human setup (P0 — Chris, not automatable)

From PR #1's checklist (memory `project_reliability_eval_pr`); the public
`health.chrispiserchia.com/health` route is already live and returning OK.

- [ ] `brew install rclone`; create R2 bucket `ai-server-backups` + API token; `rclone config` remote named `r2`
- [ ] Verify: after the next 04:00 backup, `rclone lsl r2:ai-server-backups/` lists today's tarball
- [ ] Heartbeat worker (`ops/heartbeat-worker/README.md`): `wrangler kv namespace create HEARTBEAT_KV` (paste id into `wrangler.toml`); `wrangler secret put TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`; `wrangler deploy`
- [ ] Verify: `wrangler deployments list` shows it; stop caddy for 6 min on purpose (or temporarily point the worker at a bogus URL) and confirm a Telegram alert arrives, then restore

---

### Task T4: Re-fetch the Job row so post-review + escalation see `resolved_skill` (Wave 1 PR)

**Files:**
- Modify: `src/runner/main.py` (`_process_job`, two spots: after completion ~line 216, and the failure branch ~line 282)
- Update: `.context/modules/runner/CHANGELOG.md`, append gotcha to `.context/modules/runner/skills/GOTCHAS.md`

**Interfaces:**
- Consumes: `session.run_session` already stamps `resolved_skill/model/effort` into the DB before the SDK session starts (`session.py:516-524`).
- Produces: `_maybe_review` and `_maybe_escalate` now receive a Job whose `resolved_skill` is populated. No signature changes.

- [ ] **Step 1: Completion path — insert after `log.info("job completed")`:**

```python
        # run_session stamped resolved_skill/model/effort via a separate DB
        # session; this detached instance still holds the pre-run NULLs.
        # Re-fetch so the post-hooks (review, learning) see the real skill.
        async with async_session() as s:
            fresh = await s.get(Job, job_id)
        if fresh is not None:
            job = fresh
```

- [ ] **Step 2: Failure path — replace the escalation call block:**

```python
        try:
            async with async_session() as s:
                fresh = await s.get(Job, job_id)
            await _maybe_escalate(fresh if fresh is not None else job)
        except Exception:
            log.exception("escalation attempt failed (non-fatal)")
```

- [ ] **Step 3: Run the suite** — `SERVER_ROOT=$(pwd) pipenv run pytest -q` → all pass.

- [ ] **Step 4: GOTCHAS entry (runner)** — append: "Job instances loaded in `_process_job` are detached; any column stamped by a *different* session mid-job (e.g. `resolved_skill` from `run_session`) is invisible until re-fetched. Post-hooks must re-fetch. (Bug: review/escalation dead since Phase 4; evidence job — zero `code_review_started` events before 2026-07-10.)"

- [ ] **Step 5: Runbook verification (after T5 merges, same PR):** enqueue a trivial app-patch job against a scratch project, then `psql … -c "SELECT review_outcome FROM jobs ORDER BY created_at DESC LIMIT 1;"` → non-NULL, and the audit log contains `code_review_started`/`code_review_done`.

- [ ] **Step 6: Commit** — `git commit -m "fix(runner): re-fetch Job after run_session so post-review + escalation fire"`

---

### Task T5: Fix `review.py` (SDK API + whole-session diff + tier model) (Wave 1 PR)

**Files:**
- Modify: `src/runner/review.py`
- Modify: `src/runner/session.py` (capture pre-session git HEAD)
- Test: `tests/test_review.py` (add 2 pure tests)
- Update: `.context/modules/runner/CHANGELOG.md`

**Interfaces:**
- Consumes: `settings.model_deep` from T8.
- Produces: `run_session` result dict gains `"git_head_before": str|None` and `"cwd": str`; `review.pick_diff_ref(result) -> str`.

- [ ] **Step 1: session.py — add helper + capture (top-level, near other helpers):**

```python
import subprocess

def _git_head(cwd: Path) -> str | None:
    """Pre-session HEAD so post-review can diff the whole session's work."""
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(cwd),
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None
    except Exception:
        return None
```

In `run_session`, before `client = ClaudeSDKClient(options=options)`:
```python
    git_head_before = _git_head(cwd)
```
and extend the return dict:
```python
        return {
            "summary": final_summary,
            "duration_seconds": duration,
            "usage": usage,
            "skill": skill_name,
            "cwd": str(cwd),
            "git_head_before": git_head_before,
        }
```

- [ ] **Step 2: review.py — replace the broken client loop (lines ~177-188):**

```python
    try:
        client = ClaudeSDKClient(options=options)
        final_text = ""
        async with client:
            await client.query(prompt)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            final_text += block.text
        outcome = _parse_outcome(final_text)
```

Move the imports to the top of the file:
```python
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, TextBlock
```

- [ ] **Step 3: review.py — whole-session ref + tier model:**

```python
def pick_diff_ref(result: dict | None) -> str:
    """Diff base for post-review: the pre-session HEAD when known (covers all
    commits the session made + working tree), else last commit. Pure."""
    return (result or {}).get("git_head_before") or "HEAD~1"
```

In `run_code_review`'s options: `model=settings.model_deep,` (drop the hardcoded string). In `main.py:_maybe_review`, replace `diff = get_git_diff(cwd)` with:

```python
    diff = get_git_diff(cwd, ref=pick_diff_ref(result))
```
(import `pick_diff_ref` alongside the existing review imports.)

- [ ] **Step 4: tests (tests/test_review.py):**

```python
from src.runner.review import pick_diff_ref

def test_pick_diff_ref_prefers_presession_head():
    assert pick_diff_ref({"git_head_before": "abc123"}) == "abc123"

def test_pick_diff_ref_falls_back():
    assert pick_diff_ref({}) == "HEAD~1"
    assert pick_diff_ref(None) == "HEAD~1"
    assert pick_diff_ref({"git_head_before": None}) == "HEAD~1"
```

- [ ] **Step 5: run suite; commit** — `git commit -m "fix(review): real SDK streaming API; review whole session diff; tier model"`

---

### Task T6: Startup reconciliation for stranded `queued` jobs (Wave 1 PR)

**Files:**
- Modify: `src/runner/reconcile.py`
- Modify: `src/runner/main.py` (`main()`, after `reconcile_orphaned_jobs()`)
- Test: `tests/test_orphaned_jobs.py`
- Update: `.context/modules/runner/CHANGELOG.md`, `.context/modules/runner/CONTEXT.md` (public interface), `.context/SYSTEM.md` invariant INV-15 wording

**Interfaces:**
- Produces: `reconcile.stranded_queued_ids(rows, redis_members) -> list` (pure), `reconcile.reconcile_stranded_queued() -> int`.

- [ ] **Step 1: failing tests first (tests/test_orphaned_jobs.py):**

```python
from src.runner.reconcile import stranded_queued_ids

def test_stranded_queued_ids_flags_missing_from_redis():
    rows = [("a", "queued"), ("b", "queued"), ("c", "running")]
    assert stranded_queued_ids(rows, {"b"}) == ["a"]

def test_stranded_queued_ids_empty_when_all_in_redis():
    assert stranded_queued_ids([("a", "queued")], {"a"}) == []
```

Run: `pipenv run pytest tests/test_orphaned_jobs.py -q` → FAIL (name not defined).

- [ ] **Step 2: implement in reconcile.py:**

```python
STRANDED_REQUEUE_MAX_AGE_HOURS = 24


def stranded_queued_ids(rows: Iterable[tuple], redis_members: set[str]) -> list:
    """Pure. rows = (job_id, status) pairs; return ids stuck in 'queued' with
    no matching entry in the Redis queue (crash between BLPOP and
    status=running, or a Redis restart that dropped the list)."""
    return [
        jid for jid, status in rows
        if status == JobStatus.queued.value and str(jid) not in redis_members
    ]


async def reconcile_stranded_queued() -> int:
    """Re-push stranded queued rows younger than STRANDED_REQUEUE_MAX_AGE_HOURS;
    fail older ones (their moment passed — schedules re-fire on their own).
    Runs at startup after reconcile_orphaned_jobs. Returns count handled."""
    from src.db import QUEUE_JOBS, redis

    async with session_scope() as s:
        result = await s.execute(
            select(Job.id, Job.status, Job.created_at)
            .where(Job.status == JobStatus.queued.value)
        )
        rows = list(result.all())
    if not rows:
        return 0

    members = {str(m) for m in await redis.lrange(QUEUE_JOBS, 0, -1)}
    stranded = set(stranded_queued_ids([(r[0], r[1]) for r in rows], members))
    if not stranded:
        return 0

    now = datetime.now(timezone.utc)
    handled = 0
    for job_id, _, created_at in rows:
        if job_id not in stranded:
            continue
        age_h = (now - created_at).total_seconds() / 3600
        if age_h <= STRANDED_REQUEUE_MAX_AGE_HOURS:
            await redis.rpush(QUEUE_JOBS, str(job_id))
            logger.warning("re-queued stranded job", job_id=str(job_id))
        else:
            audit_log.append(str(job_id), "job_failed",
                             error="stranded: queued row with no Redis entry",
                             error_category="stranded")
            async with session_scope() as s:
                await s.execute(update(Job).where(Job.id == job_id).values(
                    status=JobStatus.failed.value,
                    error_message="stranded queued job (startup reconciliation)",
                    completed_at=now,
                ))
            append_to_index(settings.audit_log_dir, str(job_id))
        handled += 1
    return handled
```

(Confirm `redis.lrange` returns `str` under `db.py`'s decode settings; adjust the `{str(m) …}` cast accordingly.)

- [ ] **Step 3: call it in `main.py:main()` right after the orphan reconcile:**

```python
    try:
        nq = await reconcile_stranded_queued()
        if nq:
            logger.warning("startup: reconciled stranded queued jobs", count=nq)
    except Exception:
        logger.exception("stranded-queued reconciliation failed (non-fatal)")
```
(import alongside `reconcile_orphaned_jobs`.)

- [ ] **Step 4: tests pass; docs; commit** — update runner CONTEXT public-interface list + SYSTEM.md INV-15 line ("…reconciles orphaned `running` **and stranded `queued`** jobs…"); `git commit -m "feat(runner): startup reconciliation for stranded queued jobs (INV-15 extension)"`

---

### Task T7: Router rules for the atlas family + reachability contract test (Wave 1 PR)

**Files:**
- Modify: `src/runner/router.py`
- Test: `tests/test_pure_functions.py` (router cases), `tests/test_skill_contracts.py` (reachability)
- Update: `.context/modules/runner/CHANGELOG.md`

- [ ] **Step 1: failing router tests (tests/test_pure_functions.py):**

```python
@pytest.mark.parametrize("desc,expected", [
    ("atlas-report: asset CRDO", "atlas-report"),
    ("atlas report on NVDA", "atlas-report"),
    ("atlas-chat: report 6d3a8bde-54fa", "atlas-chat"),
    ("scout stocks", "atlas-scout"),
    ("atlas-scout: run stock scout", "atlas-scout"),
    ("atlas-portfolio: I sold 4 shares of ZZAGENT", "atlas-portfolio"),
    ("daily brief", "atlas-daily-brief"),
    ("redeploy atlas", "atlas-redeploy"),
])
def test_router_atlas_family(desc, expected):
    assert router.route(desc) == expected
```

- [ ] **Step 2: add the rule block to `_RULES` — placed ABOVE the `── Research ──` section** (the research rule would otherwise swallow "atlas report on …"), and fold the existing two `redeploy atlas` rules into it:

```python
    # ── Atlas family (dispatch safety net — canonical path is enqueue-by-kind;
    #    see docs/TROUBLESHOOTING.md "skill jobs must enqueue by kind") ──
    (r"^atlas[-_]report\b|\batlas report\b", "atlas-report"),
    (r"^atlas[-_]chat\b|\batlas chat\b", "atlas-chat"),
    (r"^atlas[-_]scout\b|\bscout stocks?\b", "atlas-scout"),
    (r"^atlas[-_]portfolio\b", "atlas-portfolio"),
    (r"^atlas[-_]daily[-_]brief\b|\bdaily brief\b", "atlas-daily-brief"),
    (r"\bredeploy atlas\b|\batlas[- ](redeploy|deploy|restart|update)\b", "atlas-redeploy"),
```

- [ ] **Step 3: reachability contract test (tests/test_skill_contracts.py):**

```python
# Skills reached by kind (web app / schedules / runner-internal spawns) rather
# than by router rule. Adding a skill? Either give it a router rule or list it
# here with a comment naming its dispatcher. This is the contract that killed
# the "SKILL.md advertises a trigger nobody implements" class of bug
# (EVALUATION_2026-07-10 §3.6).
KIND_DISPATCHED = {
    "chat": "telegram /chat + JobKind.chat",
    "code-review": "runner post-review sub-agent (review.py)",
    "server-upkeep": "schedule server-upkeep-daily",
    "review-and-improve": "events.py idle-queue trigger",
    "project-update-poll": "per-project schedules",
    "atlas-report-sweep": "schedule atlas-weekly-reports",
    "god": "owner-only, explicit kind",
    "restore": "owner-only, explicit kind",  # router also matches \brestore\b
}

def test_every_skill_is_reachable():
    from src.runner import router
    targets = {skill for _, skill in router._RULES}
    skills_dir = Path(settings.server_root) / "skills"
    for d in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        name = d.name
        if name.startswith("_"):
            continue  # internal: runner-spawned
        assert name in targets or name in KIND_DISPATCHED, (
            f"skill '{name}' is unreachable: no router rule and not declared "
            f"in KIND_DISPATCHED"
        )
```

- [ ] **Step 4: run suite (router tests + contract test green); commit** — `git commit -m "feat(router): atlas-family rules + skill-reachability contract test"`

---

### Task T8: Model tier map — retire scattered `claude-opus-4-7` pins (Wave 1 PR, first in sequence)

**Files:**
- Modify: `src/config.py`, `src/runner/review.py` (T5 consumes), `src/runner/learning.py:234`, `src/runner/session.py` (`_MODEL_BUDGETS`), `src/gateway/telegram_bot.py:118-119`, `src/gateway/web.py:478-480`
- Modify: all `skills/*/SKILL.md` with `claude-opus-4-7` (10 files) + `.context/SKILLS_REGISTRY.md` prose
- Update: CHANGELOGs for runner, gateway; `SERVER.md` + `MISSION.md` model prose

- [ ] **Step 1: verify the target model works on this subscription BEFORE sweeping:**

```bash
pipenv run python3 -c "
import anyio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
async def main():
    async with ClaudeSDKClient(options=ClaudeAgentOptions(model='claude-opus-4-8', max_turns=1)) as c:
        await c.query('Reply with exactly: ok')
        async for m in c.receive_response(): pass
anyio.run(main)"
echo "exit: $?"
```
Expected: exit 0. If the model id is rejected, STOP and keep 4-7 pins; revisit.

- [ ] **Step 2: config.py — tier fields next to `default_model`:**

```python
    # Model tiers — the single place a model-generation bump happens.
    # default_model (sonnet tier) already exists above.
    model_fast: str = "claude-haiku-4-5-20251001"
    model_deep: str = "claude-opus-4-8"
```

- [ ] **Step 3: consume the tiers** — `learning.py:234` → `model=settings.model_fast`; `review.py` → `model=settings.model_deep` (in T5); `telegram_bot.py` alias map → `{"opus": settings.model_deep, "sonnet": settings.default_model, "haiku": settings.model_fast, …}` keeping explicit-id passthrough; `web.py` dropdown options rendered from the three settings; `session._MODEL_BUDGETS` → add `"claude-opus-4-8": 200_000` (keep 4-7 for historical audit parsing).

- [ ] **Step 4: frontmatter sweep:**

```bash
grep -rl "claude-opus-4-7" skills/ | xargs sed -i '' 's/claude-opus-4-7/claude-opus-4-8/g'
grep -rn "claude-opus-4-7" skills/   # expect: nothing
```
Update `SKILLS_REGISTRY.md` prose ("Opus 4.7" → "Opus 4.8 (deep tier)") and the `Opus 4.7` mentions in `SERVER.md`/`MISSION.md` to tier language ("the deep tier — see `src/config.py`").

- [ ] **Step 5: run suite + lint_docs; commit** — `git commit -m "feat(models): tier map in config; bump deep tier to opus-4-8 across skills + UI"`

---

### Task T9: Stop the INFO log spam (bot 25 MB, runner SDK lines) (Wave 1 PR)

**Files:**
- Modify: `src/gateway/telegram_bot.py` (logging setup), `src/runner/main.py:846-848`
- Update: gateway + runner CHANGELOGs

- [ ] **Step 1:** in the bot's logging setup add:

```python
    # httpx logs every getUpdates poll at INFO — with the bot token in the URL.
    logging.getLogger("httpx").setLevel(logging.WARNING)
```

In `runner/main.py` after `logging.basicConfig(level=logging.INFO)`:

```python
    # The SDK transport logs "Using bundled Claude Code CLI" per session at INFO.
    logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
```

- [ ] **Step 2:** truncate the polluted log (it contains the bot token in URLs): `: > volumes/logs/bot.err.log`. Optional hardening: rotate the Telegram bot token via BotFather since it sat in a local log for months (owner's call — log never left the Mac).

- [ ] **Step 3:** restart bot + runner (`launchctl kickstart -k gui/$(id -u)/com.assistant.bot` / `…runner`), confirm the log stays quiet for 5 minutes. Commit.

---

### Task T10: Loop-liveness checks in `server-upkeep` (direct skill commit)

**Files:**
- Modify: `skills/server-upkeep/SKILL.md` (insert after step 8b; extend step 9's DM conditions + summary format)

- [ ] **Step 1: add three checks:**

````markdown
### 8c. Local backup freshness

```bash
newest=$(ls -t volumes/backups/backup-*.tar.gz 2>/dev/null | head -1)
if [ -z "$newest" ]; then echo "NO LOCAL BACKUPS"; else
  echo "$newest age_hours=$(( ($(date +%s) - $(stat -f %m "$newest")) / 3600 ))"
fi
```

Anomaly if no backup exists or the newest is older than 26 hours. (The 04:00
timer failed silently with exit 127 for three months once — this check is the
reason that can't recur. EVALUATION_2026-07-10 §3.7.)

### 8d. launchd last-exit sweep

```bash
launchctl list | awk '$3 ~ /^com\.assistant\./ && $2 != 0 && $2 != "-" {print $3, "last_exit=" $2}'
```

Any output = anomaly (a supervised job is failing between healthchecks).

### 8e. Feedback-loop liveness

```bash
psql assistant -c "SELECT max(completed_at) FROM jobs WHERE resolved_skill='review-and-improve' AND status='completed';"
psql assistant -c "SELECT count(*) FILTER (WHERE review_outcome IS NOT NULL) AS reviewed, count(*) AS total
  FROM jobs WHERE resolved_skill IN ('app-patch','new-project','server-patch','new-skill')
  AND status='completed' AND created_at > now() - interval '7 days';"
```

Anomalies: last review-and-improve completion > 7 days ago (or never);
`total > 0` with `reviewed = 0` (post-review not stamping — the §3.3 failure
mode). A broken loop cannot report itself; this step is its external monitor.
````

- [ ] **Step 2:** add the three to the "DM the user when" list and the summary template (`Local backup: fresh (<age>) | MISSING/STALE`, `launchd: clean | <labels>`, `Loops: review-and-improve <age>, post-review <reviewed>/<total>`).

- [ ] **Step 3:** commit — `git commit -m "feat(server-upkeep): local-backup, launchd-exit, and loop-liveness checks"`

---

### Task T11: Atlas web app enqueues by `kind` (atlas DEV repo; deploy via atlas-redeploy)

**Files:** in `~/Documents/repos/atlas` — the enqueue call sites (see § 5 of the evaluation / atlas agent report for exact paths; the pattern to find them: `grep -rn "\"kind\"\|'kind'\|api/jobs" dashboard/ --include=*.ts --include=*.tsx --include=*.py`)

- [ ] **Step 1:** change chat/report/scout enqueue payloads from `kind: "task"` (or omitted) + `description: "atlas-chat: …"` to `kind: "atlas-chat" | "atlas-report" | "atlas-scout"`, keeping the human-readable description unchanged. (`atlas-portfolio` already does this — copy its call shape.)
- [ ] **Step 2:** DECISION (owner): also send `payload: {"project_slug": "atlas"}` so sessions get project cwd + the lighter project directive. Recommended: yes, but note it changes which CLAUDE.md the SDK auto-loads (atlas's own) — verify one report end-to-end after.
- [ ] **Step 3:** commit in dev repo, `/task redeploy atlas`, then verify: next atlas-chat job row shows `kind='atlas-chat'`, `resolved_skill='atlas-chat'`, and the audit log's `job_started` event carries the skill's model/max_turns.
- [ ] **Step 4:** T7's router rules remain as the safety net for hand-typed `/task` phrasings.

---

### Task T12: Repo & docs cleanup batch (direct commits, doc-only + git hygiene)

Work through `EVALUATION_2026-07-10.md` § 4 tables; one commit per row-group.

- [ ] `git rm -r .handoff/` (self-declared archived; Rec-10 shipped)
- [ ] Worktree: `git log main..feature/telegram-thread-interface --oneline` — if empty: `git worktree remove .worktrees/telegram-thread-interface && git branch -D feature/telegram-thread-interface`; if not empty, STOP and surface the unmerged commits first
- [ ] Casing sweep: `grep -rn "Troubleshooting.md" --include="*.md" --include="*.py" . | grep -v TROUBLESHOOTING` → update every hit (CLAUDE.md map, INDEX.md, `skills/god/SKILL.md` + `skills/self-diagnose/SKILL.md` `context_files`) to `docs/TROUBLESHOOTING.md`
- [ ] `SKILLS_REGISTRY.md`: delete the blank line splitting the Installed table; note the tier convention from T8
- [ ] `SERVER.md` + `router.py` docstring: remove the never-built "route skill" fallback claim ("Routing is rule-based; unmatched descriptions run as generic tasks")
- [ ] `PROJECTS_REGISTRY.md`: annotate the `research` row ("not yet bootstrapped — no schedule; see T13") or resolve via T13
- [ ] `docs/README.md`: add rows for `EVALUATION_2026-04-18.md`, `EVALUATION_2026-07-10.md`, `superpowers/plans|specs/`
- [ ] `.env.example`: add `POSTGRES_PASSWORD=changeme`
- [ ] `MISSION.md` §M: add — "`god` skill: the deliberate, owner-invoked exception to every ceiling above (bypassPermissions, direct commit+push). Exists so 'human at the terminal' work can run through the same job/audit machinery; never router-reachable, never scheduled."
- [ ] `GETSTARTED.md`/`TEARDOWN.md` refresh (4-task runner, reconcile, current plist set — market-tracker plists are gone)
- [ ] `.context/SYSTEM.md`: compress "Active workstreams" to one line per shipped phase
- [ ] Archive retired logs: `mkdir -p volumes/logs/archive && mv volumes/logs/project.market-tracker* volumes/logs/archive/`
- [ ] Prune `.claude/settings.local.json` one-shot entries (keep durable patterns: psql, pipenv run, launchctl list, curl, ls, git clone)
- [ ] Stamp the status table in `EVALUATION_2026-07-10.md` as tasks land

---

### Task T13: DECISION — seed the missing MISSION-B/E schedules, or descope

MISSION objectives B (scheduled research) and E (idea generation) currently
have zero schedule rows; `seed-schedules.sh` only seeds upkeep.

- [ ] Owner picks: (a) seed both (recommended), (b) descope MISSION text
- [ ] If (a): add to `scripts/seed-schedules.sh` (topic placeholder needs an owner choice):

```bash
upsert 'research-weekly' '0 13 * * 1' 'research-report' 'Weekly research report: <OWNER: pick standing topic>'
upsert 'ideas-weekly'    '0 14 * * 1' 'idea-generation' 'Generate 3-5 ideas for the assistant server or its projects'
```
run it, verify `psql assistant -c "SELECT name, cron_expression FROM schedules;"` shows 5 rows; first `research-report` run bootstraps `projects/research/`, resolving the registry annotation from T12.

---

### Task T14: Eval-harness baseline + coverage for the highest-volume skills

- [ ] Read `evals/README.md`; run the harness per its instructions for the 3 existing cases; commit the baseline scores it produces into `evals/results/` if the README says results are trackable, else record them in the eval doc status table
- [ ] Add `evals/cases/atlas-report.yml` and `evals/cases/self-diagnose.yml` following the existing case schema (input + rubric + baseline_score); atlas-report's rubric should key off the deterministic evaluator contract (citations within 2%, ≥2 risks, no promise language)
- [ ] Verify `skills/review-and-improve/SKILL.md` actually references running the harness (PR #1 claimed the wiring) — if absent, add it

---

### Task T15: DECISION — plugin exposure for SDK job sessions

Today all 6 plugins (incl. superpowers' mandatory-skill SessionStart hook)
load into every job via project settings + `setting_sources=["project"]`;
17 jobs have used the Skill tool. Powerful for god/builder sessions, costly
for 12-turn atlas answers.

- [ ] Owner picks: (a) status quo, (b) per-skill opt-out (recommended), (c) move plugins to user-level settings (removes from ALL jobs incl. god)
- [ ] If (b): add `setting_sources: []` support — `SkillConfig` gains `setting_sources: list[str] | None = None` (`src/registry/skills.py`); in `session.py:_build_options` replace the hardcoded value with `skill_cfg.setting_sources if skill_cfg and skill_cfg.setting_sources is not None else ["project"]`; set `setting_sources: []` in the frontmatter of: chat, project-update-poll, atlas-chat, atlas-report, atlas-scout, atlas-portfolio, atlas-daily-brief, _writeback, _learning_apply. Note in each: "skips project settings: no plugins, no server CLAUDE.md — this skill body is self-contained." Ship inside a server-patch PR (touches src/) with a router-style pure test for the resolution precedence.

---

### Task T16: Atlas project remediation (from `docs/EVALUATION_2026-07-10-atlas.md`)

All dev-repo work happens in `~/Documents/repos/atlas` (never the runtime
clone), then ships via `/task redeploy atlas`. Suitable for `app-patch` /
owner sessions; T11 can ride the same deploy.

**Dev repo (`~/Documents/repos/atlas`):**
- [ ] Create `.context/CONTEXT.md` with EXACTLY the 5 standard sections (Mission, Platforms, Web Serving, Architecture, Status) — distill from README + manifest; and `.context/CHANGELOG.md` (seed it with the 4 missing commit entries: 28efaae, 99f1244, 5f68c17, bfe011c, 7f5b9e3; decide whether root `CHANGELOG.md` becomes a symlink/pointer)
- [ ] `CLAUDE.md`: perimeter row "Tailnet-only" → "Cloudflare Access (CF edge auth; Caddy → :8791 local)"; Models row → "subscription auth via ai-server skills; in-process LLM paths key-less by policy"
- [ ] `manifest.yml`: remove `ANTHROPIC_API_KEY` from `env_required`; set `git.repo` to the real remote
- [ ] Learn-loop fix (structural): relocate `dashboard/experts_knowledge/` to an untracked var dir (packet already emits absolute `knowledge_path`); rescue the pending `crypto_analyst.md` line first; seed empty `market_analyst.md` + `report_critic.md` so emitted paths exist
- [ ] pm-edge: fix or quiet `rates_implied` (alternate ZQ source per `docs/DATA_SOURCES.md`, or hourly backoff + single summary line)
- [ ] Hygiene: `git rm --cached .DS_Store`; add `.DS_Store` + `*.egg-info/` to `.gitignore`; historical banners on `docs/DEPLOY_RUNBOOK.md` + `docs/MARKET_TRACKER_INTEGRATION.md` + DORMANT banner on crew docs; rotate `docs/SESSION_HANDOFF.md` (keep current picture + last 2–3 sessions); resolve root `PROGRESS.md` (merge or declare canonical)
- [ ] Verify deploy-gate pytest isolation targets `atlas_test` (ZZAGENT note in the report § 5)
- [ ] Consider a Python lockfile (uv/pip-tools) for reproducible redeploys

**Server repo:**
- [ ] `.context/PROJECTS_REGISTRY.md`: atlas paragraph "Three dedicated skills" → the current seven
- [ ] `skills/atlas-redeploy/GOTCHAS.md`: fix the pointer to atlas `docs/TROUBLESHOOTING.md` (doesn't exist) → this repo's `docs/TROUBLESHOOTING.md` §"atlas redeploy reports diverged"
- [ ] `skills/atlas-report-sweep/SKILL.md`: soften the stale "Kraken BTC feed broken" gotcha (feed healthy since fix)

**Runtime clone (human-confirmed, no git writes by agents):**
- [ ] Delete `.superpowers/sdd/` scratch after confirming mirrored/obsolete
- [ ] Delete branch `backup-2026-07-09` after confirming nothing unique on it

---

### Task T17: Backlog (each needs an owner nod before starting)

- [ ] **baseball-bingo audit** — the April memory records a promised "full audit + mission statement + documentation pass" post-migration; run `project-evaluate` on it (this also gives the fixed post-review path a real exercise)
- [ ] **Quality-signal harvesting** — atlas's deterministic evaluator scores + (now-working) review outcomes into the retrospective instead of relying on manual /rate (2 ratings in 3 months)
- [ ] **sudo capability for self-diagnose** — April feedback memory asks for autonomous tunnel/plist/Caddy repair; decide between a scoped NOPASSWD helper script vs. keeping human-in-loop; document the decision in MISSION §M either way
- [ ] **audit INDEX backfill** — `audit_index.rebuild_index` records `skill: ""` for the historical mis-dispatched jobs; backfill from `jobs.resolved_skill` so retrospectives over old data aren't blind

---

## Self-review notes

- Spec coverage: every § 3 defect in the evaluation maps to a task (A→T4, B→T5, C→T1+T6, D→T7+T11, E→T2+T3+T10); § 3.11 gaps map to T7/T10/T13/T14/T15/T17; § 4 tables map to T2/T12.
- Types/names consistent: `pick_diff_ref` (T5) consumed in T4's runbook via `_maybe_review`; `stranded_queued_ids` signature matches its tests; `settings.model_deep` introduced in T8, consumed in T5 — hence T8 first in the PR sequence.
- Known unknowns called out inline rather than papered over: redis decode cast (T6), evals CLI flags (T14), atlas enqueue file paths (T11 → agent report), opus-4-8 availability gate (T8 step 1).
