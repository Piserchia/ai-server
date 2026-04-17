# Assistant Server — System Design

*Chris · 2026-04-16 · Design document (no code yet)*

This doc specifies the entire system before any code is written. Every workflow, every model choice, every feedback loop, every write-back rule. Review, push back, iterate — then we build against this spec.

**Scope of what this document covers:**

1. One-paragraph mission + what the system explicitly is *not*
2. High-level architecture + the six nouns that matter
3. Complete skill / workflow catalog (18 skills, one row per skill)
4. Orchestration: how a job flows from message to completion
5. Model selection framework — the declarative + escalation + auto-tuning design
6. Context & documentation — the nervous system that makes continuity work
7. Self-evaluation — quality gates, review jobs, retrospectives
8. Self-improvement — signals, actions, triggers, gates
9. Self-management — healthchecks, diagnosis, recovery, budgets
10. Self-expansion — new projects, new skills, server-patch
11. Hooks, sub-agents, custom MCP tools
12. Key invariants — hard rules the system must never violate
13. What builds first (MVP) vs what builds later

---

## 1. Mission & scope

**Mission**: a personal assistant server on your Mac Mini that *manages, maintains, patches, and extends itself and a growing catalog of projects* via natural-language requests from Telegram or the web, using the Claude Agent SDK as its execution engine. You tell it "weekly NBA injury report" or "new project: crypto portfolio dashboard" or "market-tracker is throwing NaN on weekends — fix it," and the right thing happens, documented, with minimal babysitting.

**This is not:**
- A general-purpose agent framework (you've been burned by that)
- A multi-user SaaS — single-tenant, your server, your chat IDs only
- A replacement for Claude Code for interactive coding — you'll still open Claude Code on your laptop for big refactors
- A "feels like a human" conversational companion — the interaction style is: you give tasks, it does them, it reports back
- Something that self-modifies server code without your approval — changes to the server always go through a PR gate

**Hard ceilings the system must respect:**
- ~$5/day default spend (overridable)
- 3 concurrent jobs max (overridable)
- 30-minute max session by default
- Server code changes never auto-deploy; they always open a PR and alert you

---

## 2. Architecture

### 2.1 The six nouns

The whole system is built from six concepts. Internalize these and the rest of the design follows.

| Noun | What it is | Where it lives |
|---|---|---|
| **Job** | One unit of work. Always has a `kind`, a `description`, a `status`. May be scoped to a project. | Postgres `jobs` table + JSONL audit log on disk |
| **Skill** | A markdown file telling Claude how to do a kind of work. Data, not code. | `skills/<name>/SKILL.md` (+ optional support files) |
| **Project** | A hosted deliverable (static site, service, or API) with its own subdomain. | `projects/<slug>/` directory with `manifest.yml` + its own `.context/` |
| **Schedule** | A cron expression that enqueues a job on a recurrence. | Postgres `schedules` table |
| **Manifest** | Per-project YAML declaring how to run, host, update, and health-check it. | `projects/<slug>/manifest.yml` |
| **Audit log** | Append-only JSONL of everything that happened on a job. Permanent memory. | `volumes/audit_log/<job_id>.jsonl` |

If a future feature can be expressed as "a new job kind + a skill that handles it," build it. If it needs a seventh noun, think harder — usually it doesn't.

### 2.2 Process topology

```
                       ┌──────────────────────────────────────────────┐
                       │                  Mac Mini                      │
                       │                                                │
 Telegram ──► bot ──┐  │  ┌─── Redis ───┐    ┌─────────────────────┐  │
                    ├──┼──► jobs:queue  ├──► │  runner              │  │
 Web UI ─► web  ───┤  │  │ jobs:stream  │    │  ┌───────────────┐   │  │
                    │  │  │ jobs:cancel │ ◄──┤  │ Agent SDK     │   │  │
 Cron ───► sched ──┘  │  │ jobs:done   │    │  │ (ClaudeSDK    │   │  │
                       │  └─────────────┘    │  │  Client       │   │  │
                       │                     │  │  sessions)    │   │  │
                       │                     │  └───────────────┘   │  │
                       │                     │   spawns children    │  │
                       │                     └──────────┬───────────┘  │
                       │                                │               │
                       │  Postgres ◄────────────────────┤               │
                       │  (jobs, schedules, projects)   │               │
                       │                                ▼               │
                       │                    volumes/audit_log/*.jsonl  │
                       │                    skills/, projects/         │
                       │                                                │
                       │  ┌─── Caddy ─────────────────────────────┐    │
                       │  │ yourdomain.com  → web:8080             │    │
                       │  │ *.yourdomain.com → per-project routes │    │
                       │  └────────────────────▲──────────────────┘    │
                       └────────────────────── │ ─────────────────────┘
                                               │ TLS (public)
                                       Cloudflare Tunnel
                                       (named, stable)
                                               │
                                      Internet (you, anywhere)
```

**Four long-running processes** (managed by launchd, each with its own plist):

1. **runner** — consumes `jobs:queue`, runs Agent SDK sessions, writes audit logs
2. **web** — FastAPI dashboard + `/api/jobs` REST, on `localhost:8080`
3. **bot** — Telegram polling + notification DMs on job completion
4. **caddy** — reverse proxy; routes `*.yourdomain.com` to projects, `yourdomain.com` to the dashboard
5. **cloudflared** — tunnel agent; connects your Mac to Cloudflare's edge (runs as a system service via `sudo cloudflared service install`)

Everything else (the scheduler, cancel listener, healthcheck loop) runs *inside* the runner as async tasks — not as separate processes. The old system had 9 loops in one file; the new one has 3 (job consumer, scheduler, healthcheck). Clear.

---

## 3. Skill catalog

Every unit of repeatable work is a skill. A skill is a markdown file. Its YAML frontmatter declares model/effort/permission defaults and required tools. Its body is prose instructions Claude reads every time.

### 3.1 Full catalog (18 skills)

| # | Skill | Trigger | Model / Effort (default) | Permission | Purpose |
|---|---|---|---|---|---|
| 1 | `chat` | `/chat <msg>` | Sonnet 4.6 / low | default | One-shot conversation, no tools, no project context |
| 2 | `route` | internal | Haiku 4.5 / low | default | Pick a skill from natural-language `/task`. Rule-based first, this LLM call is fallback for ambiguous inputs. |
| 3 | `research-report` | scheduled or `/task research <topic>` | Sonnet 4.6 / medium | acceptEdits | Web search + synthesis → `projects/research/<topic>-<date>.md` |
| 4 | `research-deep` | `/task deep research <topic>` | Opus 4.7 / high | acceptEdits | Longer-form, 1M-context, multi-source investigation |
| 5 | `idea-generation` | scheduled or `/task ideas for <domain>` | Sonnet 4.6 / medium | default | Structured idea generation; dedupes against history.jsonl |
| 6 | `new-project` | `/task new project: <desc>` | Sonnet 4.6 / medium → Opus 4.7 if complex | acceptEdits | Scaffold, register, deploy a new project |
| 7 | `new-skill` | `/task new skill: <desc>` | Opus 4.7 / high | plan → acceptEdits | Author a new SKILL.md + support files; register in SKILLS_REGISTRY.md |
| 8 | `app-patch` | `/task fix <project>: <issue>` | Opus 4.7 / high | acceptEdits | cd into a project, fix a bug, commit, redeploy |
| 9 | `code-review` | internal (pre-merge) | Opus 4.7 / high | plan (read-only) | Review a diff; output LGTM / changes-requested / blocker |
| 10 | `self-diagnose` | auto on 2x failure, or `/task diagnose <issue>` | Opus 4.7 / high | acceptEdits | Read audit logs, identify cause, propose or apply fix |
| 11 | `server-patch` | `/task server: <change>` | Opus 4.7 / xhigh | **plan** → human approval → acceptEdits | Modify server code; opens a PR; never auto-applies |
| 12 | `server-upkeep` | cron `0 3 * * *` | Sonnet 4.6 / low | acceptEdits | Daily: log rotation, DB cleanup, cert check, disk, anomaly report |
| 13 | `healthcheck-all` | every 5 min | *no LLM* | *no LLM* | Pure script; hits every project's `/health`, updates `projects.last_healthy_at` |
| 14 | `project-update-poll` | per-project cron | Haiku 4.5 / low (or *no LLM*) | acceptEdits | Runs each project's declared `on_update.command`; LLM only if the update needs reasoning |
| 15 | `backup` | cron `0 4 * * *` | *no LLM* | *no LLM* | pg_dump + tar projects/ → off-site rsync |
| 16 | `restore` | `/task restore <backup-id>` | Sonnet 4.6 / medium | acceptEdits | Interactive: validate backup, confirm scope, apply |
| 17 | `review-and-improve` | cron `0 0 1 * *` (monthly) + `/task review` | Opus 4.7 / max | **plan** | Monthly retrospective. Proposes changes as PRs, never applies. |
| 18 | `notify` | internal | *no LLM* | *no LLM* | Utility: send to Telegram/email/Slack. Used by other skills. |

### 3.2 Why these skills, no more

The 18 cover your stated wants (research reports, new apps, idea generation, self-debug, deployment, multi-project hosting) plus the things you'd discover you need within a month (healthchecks, backups, upkeep, review). A bigger catalog would be premature. The system is designed so that when a pattern repeats 3 times across manual `/task` requests, you (or `new-skill`) turn it into a skill #19.

### 3.3 SKILL.md schema

```markdown
---
# YAML frontmatter — parsed by the runner to set SDK options
name: research-report
description: Web research + synthesis into a markdown report
model: claude-sonnet-4-6       # overrides settings.default_model
effort: medium                 # low | medium | high | xhigh | max
permission_mode: acceptEdits
required_tools: [Read, Write, WebSearch, WebFetch, Bash]
max_budget_usd: 1.0
max_turns: 30
escalation:
  on_failure:
    model: claude-opus-4-7
    effort: high
  on_quality_gate_miss:
    model: claude-opus-4-7
    effort: high
tags: [research, writing]
---

# Research Report

## When to use
Trigger keywords: "research", "report", "summarize", "weekly update", "market summary".
Accepts: a topic, optionally a depth (quick|standard|deep) and output path.

## Inputs you will receive via payload
- `topic` (string, required)
- `depth` (enum, default=standard)
- `output_path` (default=`projects/research/`)
- `notify_chat_id` (optional — Telegram chat to DM the TL;DR)

## Procedure
1. If `topic` is ambiguous or dated (e.g., refers to "the election" without specifying which),
   use AskUserQuestion to disambiguate before searching.
2. Run 2-5 WebSearch queries, short (1-6 words). Prefer recent results for current topics.
3. For each result that looks primary (official sites, SEC, peer-reviewed, gov), WebFetch it.
4. Paraphrase findings. Do not quote more than 15 words from any single source.
5. Write `<topic-slug>-YYYY-MM-DD.md` with these sections:
   - **TL;DR** — 3 sentences max
   - **Findings** — bulleted or prose, with inline citations
   - **Open questions**
   - **Sources** — numbered, with URLs and access dates
6. Commit the file (`git add && git commit -m "Research: <topic>"`).
7. If `notify_chat_id` set, use the `notify` MCP tool to DM the TL;DR.

## Quality gate (run before declaring done)
- [ ] At least 3 distinct primary sources cited
- [ ] No verbatim quotes over 15 words
- [ ] TL;DR is ≤ 3 sentences
- [ ] All source URLs accessible (HEAD check)
- [ ] File committed to git

If any check fails, iterate. If iteration doesn't fix it within 3 tries, write a
`## Limitations` section to the report explaining what couldn't be verified, then finish.

## Gotchas (living section — append when you learn something)
- Disambiguate people by role and location when multiple public figures share a name.
- For financial topics, the last 24h is usually more useful than the last 30d.

## Files to update as part of write-back
- `projects/research/.context/CHANGELOG.md` (append entry)
- This file's `## Gotchas` section (if you learned something non-obvious)
```

Every skill follows this pattern. The YAML frontmatter is the *machine-readable contract*; the body is the *human-and-Claude-readable instructions*.

---

## 4. Orchestration: the life of a job

### 4.1 The happy path

```
1. You: /task research the 2026 NBA trade deadline and how it affects player props
     ↓
2. Telegram bot:
     - validates chat_id is allowed
     - creates Job row: kind=task, status=queued, description=...
     - RPUSH jobs:queue <job_id>
     - stores job_id→chat_id mapping in memory (for DM on completion)
     - replies: "Queued as abc12345. I'll DM you when it's done."
     ↓
3. Runner (job_loop):
     - BLPOP jobs:queue → abc12345
     - loads Job row, sets status=running, started_at=now
     - calls route_skill(description) → returns "research-report"
          → rule-based (keyword "research" matches) — no LLM needed
     - resolves model/effort from skills/research-report/SKILL.md frontmatter
     - resolves cwd: no project scope → cwd = SERVER_ROOT
     - builds ClaudeAgentOptions(
           cwd=..., model="claude-sonnet-4-6", effort="medium",
           permission_mode="acceptEdits", session_id=str(abc12345),
           setting_sources=["project"],
           system_prompt=SERVER_DIRECTIVE + SKILL.md body,
           allowed_tools=[Read,Write,Edit,Bash,Glob,Grep,WebSearch,WebFetch,AskUserQuestion],
           hooks={PreToolUse:[_audit_tool_pre], PostToolUse:[_audit_tool_post], ...},
           max_budget_usd=1.0, max_turns=30
       )
     - registers client in _running_sessions[abc12345] = client (for /cancel)
     - opens ClaudeSDKClient; calls client.query(description)
     ↓
4. Agent SDK session:
     - Claude reads server CLAUDE.md, skills/research-report/SKILL.md
     - runs 3 WebSearch calls, 6 WebFetch calls
     - writes projects/research/nba-trade-deadline-2026-04-16.md
     - runs `git add && git commit`
     - runs its quality gate (self-check)
     - writes a final TextBlock with the TL;DR (this is captured as the summary)
     ↓
5. Runner (concurrently, per SDK message):
     - each AssistantMessage TextBlock → audit_log.append("text", ...)
     - each ToolUseBlock → audit_log.append("tool_use", ...) + publish to jobs:stream:abc12345
     - each ToolResultBlock (in UserMessage) → audit_log.append("tool_result", ...)
     - ResultMessage at end → capture cost_usd, usage
     ↓
6. Runner (post-session):
     - audit_log.write_summary(abc12345, final_text)
     - update Job: status=completed, result={summary, cost_usd, duration, usage}, completed_at=now
     - publish to jobs:done:abc12345
     - write-back verification: did we touch `projects/research/.context/CHANGELOG.md`?
          if yes → done
          if no → spawn a 60-second follow-up session with just the write-back prompt
     ↓
7. Bot (done_listener):
     - receives jobs:done:abc12345
     - looks up job_id → chat_id
     - DMs you: "Job abc12345 completed. [TL;DR here]. Full report at volumes/..."
```

That's the whole orchestration. Roughly 300 lines of Python to implement end-to-end.

### 4.2 The unhappy paths

**Cancellation**:
- `/cancel abc12345` → bot publishes to `jobs:cancel` channel with job_id
- Runner cancel_listener receives, calls `session.interrupt(job_id)` → SDK's `client.interrupt()`
- Session raises, runner catches, marks job cancelled, publishes done

**Timeout**:
- Runner wraps `run_session` in `asyncio.wait_for(timeout=1800)`
- On timeout, interrupt + mark failed with `error_message="session_timeout"`

**Failure**:
- Exception in session → log to audit, mark failed
- Event trigger listener counts consecutive failures per skill; 2 in 10 min → enqueue `self-diagnose` with the failing job_id in payload

**Budget exceeded**:
- SDK's `max_budget_usd` aborts the session mid-flight; it counts as a failure
- Daily spend tracked separately: runner queries Anthropic usage API every hour; at 80% of cap, Telegram warning; at 100%, pause the queue (don't drain; jobs accumulate)

**Ambiguous input** (AskUserQuestion):
- SDK asks a clarifying question → runner marks status=awaiting_user, publishes the question to Telegram
- User replies; bot detects it's in reply to an awaiting_user job, feeds answer back via SDK's pending-question mechanism
- Status → running

### 4.3 Concurrency

- Semaphore-gated at `settings.max_concurrent_jobs` (default 3)
- Jobs beyond the limit stay in Redis queue — no busy-waiting, no polling storm
- Anthropic rate limits are pooled across Opus 4.6/4.7, so mixed-model concurrency is fine
- Different jobs can share the filesystem (read-mostly); two sessions writing to the same project is rare in practice but protected by git (if both commit, one merges after the other)

---

## 5. Model selection framework

This is the piece you explicitly wanted me to think hard about. Three-layer design: **declarative**, **escalation**, **auto-tuning**.

### 5.1 The current model landscape (grounded in today's pricing/benchmarks)

| Model | Input $ / MTok | Output $ / MTok | Extended thinking | Notes |
|---|---|---|---|---|
| **Opus 4.7** (`claude-opus-4-7`) | $5 | $25 | low/medium/high/xhigh/max | Released today. Step-change in agentic coding. Stricter instruction-following than 4.6 — skills need to be explicit. New tokenizer uses up to 35% more tokens. |
| **Opus 4.6** (`claude-opus-4-6`) | $5 | $25 | low/medium/high/max | Still excellent for finance/science reasoning. |
| **Sonnet 4.6** (`claude-sonnet-4-6`) | $3 | $15 | low/medium/high/max | 79.6% SWE-bench (vs Opus 4.6's 80.8%). 2x faster. 30% fewer tokens in practice. Right default for 80% of work. |
| **Haiku 4.5** (`claude-haiku-4-5-20251001`) | $1 | $5 | none | 73.3% SWE-bench. For routing, classification, simple ops at volume. No extended thinking. |

**Permission modes** (SDK): `default` (prompt per tool), `acceptEdits` (auto-accept file edits), `bypassPermissions` (anything goes — use only with narrow `allowed_tools`), `plan` (write a plan, don't execute).

### 5.2 Layer 1 — Declarative defaults in SKILL.md frontmatter

Every skill declares its own `model`, `effort`, `permission_mode`. The runner reads the frontmatter and passes it to `ClaudeAgentOptions`. This is the fast path and what runs 95% of the time.

Defaults I propose (you tune over time):

| Skill | Model | Effort | Permission | Rationale |
|---|---|---|---|---|
| chat | sonnet-4-6 | low | default | Fast, conversational, zero stakes |
| route | haiku-4-5 | low | default | 50-token classification, cheapest viable |
| research-report | sonnet-4-6 | medium | acceptEdits | Most research isn't reasoning-bound; it's synthesis |
| research-deep | opus-4-7 | high | acceptEdits | Long-horizon, multi-source, worth the cost |
| idea-generation | sonnet-4-6 | medium | default | Creative but not frontier-reasoning |
| new-project | sonnet-4-6 | medium | acceptEdits | Scaffolding is mostly file-creation; escalate if stack is novel |
| new-skill | opus-4-7 | high | plan → acceptEdits | Writing a skill that future Claude reads = meta-work, worth Opus |
| app-patch | opus-4-7 | high | acceptEdits | 4.7's step-change in agentic coding matters here |
| code-review | opus-4-7 | high | plan | Plan mode = output-only, can't mutate files |
| self-diagnose | opus-4-7 | high | acceptEdits | Needs to reason across logs + code + state |
| server-patch | opus-4-7 | xhigh | plan | Maximum care when touching the server itself |
| server-upkeep | sonnet-4-6 | low | acceptEdits | Routine; Haiku isn't quite reliable enough for the edge cases |
| project-update-poll | haiku-4-5 | low | acceptEdits | Most are "run a script"; skip LLM if manifest declares `no_llm: true` |
| backup / healthcheck-all / notify | *no LLM* | — | — | Pure scripts |
| restore | sonnet-4-6 | medium | acceptEdits | Validation + interactive; not frontier |
| review-and-improve | opus-4-7 | max | plan | Once a month, best judge, read-only |

**Frontmatter override precedence** (highest wins):
1. Per-request override in job payload (`payload.model`, `payload.effort`) — from `/task --model=opus-4-7 ...` or web form
2. Skill frontmatter
3. Server default (`settings.default_model`)

### 5.3 Layer 2 — Rule-based escalation

Each SKILL.md frontmatter can declare `escalation` rules:

```yaml
escalation:
  on_failure:            # prior attempt of same kind failed
    model: claude-opus-4-7
    effort: high
  on_quality_gate_miss:  # skill's own quality gate failed twice
    model: claude-opus-4-7
    effort: xhigh
  on_low_confidence:     # runner detects low token count + high speed (suspicious)
    model: claude-opus-4-7
    effort: high
```

The runner resolves the config by:
1. Check `model_escalation_state` table (is this skill/project combo currently escalated?)
2. If yes, use escalated config; else use frontmatter default
3. On escalated run success, decay the escalation (reset to default after 24h)

This replaces the old system's complex `feedback_loop.py` with a small state table and a straightforward rule.

### 5.4 Layer 3 — Auto-tuning defaults (the quiet self-improvement signal)

Every job records `{skill, model, effort, permission_mode, outcome, cost_usd, duration_s, user_rating}` into a rollup view. Once a skill has 20+ runs:

- If a *cheaper* config has ≥ equivalent success + rating, the `review-and-improve` skill proposes lowering the default
- If a *more expensive* config would have rescued ≥ 20% of failures, proposes raising the default
- Proposals are always presented as PRs to the skill's SKILL.md; you approve or reject
- No auto-changes to defaults — this is a suggestion loop, not a silent optimizer

This gives you the benefit of the "self-improver" without the brittleness of the old system's autonomous proposal approval loop.

### 5.5 Special notes on Opus 4.7 specifically

- It's stricter about instruction-following than 4.6. Skills written for 4.6's inference-from-vagueness will misbehave. Write SKILL.md instructions as *explicit imperatives*, not suggestions. "You must paraphrase, never quote more than 15 words" not "try to paraphrase when possible."
- New tokenizer → ~35% more tokens for the same text. Keep this in mind for cache warming; prompt caching offsets most of it.
- xhigh effort is new for 4.7. Reserved for `server-patch` only. Don't use as a default anywhere else — it's slow and expensive.

---

## 6. Context & documentation — the nervous system

This is the piece that makes the system work *over time*. Every other component either feeds into it or reads from it.

### 6.1 Five-layer hierarchy

```
Layer 1: Server-level (global, rarely changes)
  ~/ai-server/CLAUDE.md                  # 20-line directive, points to the rest
  ~/ai-server/SERVER.md                  # server architecture overview
  ~/ai-server/.context/SYSTEM.md         # module graph, conventions, active workstreams
  ~/ai-server/.context/PROTOCOL.md       # the write-back protocol (copy from old repo — it's good)
  ~/ai-server/.context/SKILLS_REGISTRY.md    # all skills + one-line summaries
  ~/ai-server/.context/PROJECTS_REGISTRY.md  # all projects + manifests' key fields

Layer 2: Module-level (server code)
  ~/ai-server/.context/modules/<module>/
    CONTEXT.md        # what this module does, its public API, dependencies
    CHANGELOG.md      # chronological record of changes (appended by every touching session)
    skills/
      DEBUG.md        # bugs encountered + how they were fixed
      PATTERNS.md     # how to correctly extend this module
      GOTCHAS.md      # traps — things that look like they should work but don't

Layer 3: Skill-level
  ~/ai-server/skills/<skill>/
    SKILL.md          # the skill itself (IS the instruction)
    GOTCHAS.md        # appended when a session learns something about this skill
    examples/         # optional: past successful outputs as reference

Layer 4: Project-level
  ~/ai-server/projects/<slug>/
    CLAUDE.md         # 15-line project directive (points to server CLAUDE.md too)
    manifest.yml
    .context/
      CONTEXT.md
      CHANGELOG.md
      skills/
        DEBUG.md, PATTERNS.md, GOTCHAS.md

Layer 5: Job-level (ephemeral + permanent)
  ~/ai-server/volumes/audit_log/<job_id>.jsonl         # every tool use, every text block
  ~/ai-server/volumes/audit_log/<job_id>.summary.md    # human-readable summary
```

### 6.2 Read protocol (what every session reads before acting)

Enforced by the Agent SDK's `setting_sources=["project"]` + the skill's explicit read instructions.

```
1. ~/ai-server/CLAUDE.md                        (always)
2. system_prompt = SERVER_DIRECTIVE + SKILL.md body   (injected by runner)
3. ~/ai-server/.context/SYSTEM.md               (if touching server code)
4. ~/ai-server/.context/modules/<x>/CONTEXT.md  (if touching module x)
5. ~/ai-server/.context/modules/<x>/skills/GOTCHAS.md  (always, when touching module x)
6. projects/<slug>/CLAUDE.md                    (if project-scoped)
7. projects/<slug>/.context/CONTEXT.md          (if project-scoped)
8. Last 20 entries of volumes/audit_log/<recent_related_jobs>.jsonl   (for debug/patch jobs)
```

Total context load: typically 5-10K tokens, deterministic, happens at session start.

For debug jobs specifically, the runner pre-loads the failing job's audit log and any related prior jobs (same project, same skill, last 30 days) into a synthetic `# Prior context` block in the system prompt. This is the "future Claude picks up where past Claude left off" mechanism you wanted.

### 6.3 Write-back protocol (what every session writes before finishing)

Copied wholesale from your existing `.context/PROTOCOL.md` — it's already well-designed. Summary:

**After making changes, before declaring done:**

1. Update `.context/modules/<x>/CHANGELOG.md` for every module touched:
   ```markdown
   ## 2026-04-16 — Fix decision engine edge case
   **Agent task**: Fix INV-8 violation in decision engine
   **Files changed**:
   - `src/decision_engine.py` — added guard for empty eval_scores
   **Why**: Prevented IndexError when evaluator returns zero dimensions
   **Side effects**: None; pure function
   **Gotchas discovered**: Evaluator can return [] if all dimensions failed to parse
   ```
2. Update `.context/modules/<x>/CONTEXT.md` only if the public interface changed
3. Update relevant skill files if something non-obvious was learned:
   - `DEBUG.md` if a bug was found — symptom, root cause, fix, diagnostic shortcut
   - `PATTERNS.md` if a reusable pattern emerged
   - `GOTCHAS.md` if a trap was hit
4. Update `.context/SYSTEM.md` if module graph changed or tech debt resolved
5. If changed module A's API and module B depends on A, add a warning note to B's CONTEXT.md
6. Write a one-paragraph `<job_id>.summary.md` — what was done, what's left, where the code lives

### 6.4 Enforcement — the "it really gets written" guarantee

Three mechanisms:

1. **Skill-level prompting**: every SKILL.md ends with a "Files to update as part of write-back" list. Opus 4.7's stricter instruction-following helps here.

2. **Runner-level verification**: after `run_session` returns, the runner checks git diff. If files were modified outside `.context/`, `CHANGELOG.md`, or a skill file, it spawns a 60-second follow-up session with the prompt "Your previous session modified code but didn't update CHANGELOG.md. Do only the write-back." This is cheap (single-turn Sonnet) and guarantees write-back completeness.

3. **Git pre-commit hook** (on server repo + each project repo): blocks commits that touch `src/` without touching at least one `CHANGELOG.md`. This is the hard gate. The hook is installed by the `new-project` skill and by the server's bootstrap script.

### 6.5 Queryable history

JSONL is grep-friendly but not SQL-friendly. Compromise: the runner also writes a small rollup row per job to a `job_events` view in Postgres — `{job_id, ts, kind, project_id, skill_name, tool_uses_count, cost_usd, summary_text, outcome}`. The dashboard queries this; the full audit log is the source of truth on disk.

---

## 7. Self-evaluation

Three mechanisms, chosen for cost and reliability.

### 7.1 Quality gates inside skills (free, inline)

Every SKILL.md has a "Quality gate" section with checkboxes. The model self-checks before declaring done. This works because:
- The checks are in the same context window as the work — Claude has the output in mind
- Opus 4.7's self-verification is explicitly improved (per release notes: "actively verifies its own outputs before reporting back")
- Zero additional cost — happens in the same session

Not perfect. Claude can rationalize passing a check. But 80% effective for 0% additional spend is the right trade.

### 7.2 Targeted review jobs (high-value, selective)

For a subset of job kinds, the runner automatically spawns a `code-review` sub-agent after the primary session completes. The sub-agent runs in **plan mode** (read-only; no tool execution) with **Opus 4.7 / high**. It reads the diff and outputs: `LGTM` / `changes-requested` / `blocker`.

Triggers (declared in SKILL.md frontmatter):

```yaml
post_review:
  trigger: always | on_server_code_changes | on_project_apps | never
  reviewer_model: claude-opus-4-7
  reviewer_effort: high
```

Kinds that get auto-review: `app-patch`, `server-patch`, `new-project`. Kinds that don't: `research-report`, `chat`, `idea-generation`, `server-upkeep`.

The reviewer's output is appended to the audit log as a `review` event. If `blocker`: runner marks the job `awaiting_user` and Telegrams you the concern. If `changes-requested`: spawns a remediation session. If `LGTM`: proceeds.

This replaces your old evaluator/decision-engine stack with a simpler, more auditable thing: a second Claude looking at the output with full context and authority to stop the flow.

### 7.3 Retrospective analysis (batched, monthly)

The `review-and-improve` skill runs on the first of every month. It:

1. Queries Postgres `job_events` view for the last 30 days
2. Computes per-skill stats: success rate, median duration, median cost, user rating avg
3. Identifies patterns: a skill's failure rate spiked after date X; skill Y's cost is 2x budget; skill Z is approved 100% of its PRs but nothing else's suggestions
4. Reads the audit logs for a sample of failures
5. Proposes changes:
   - Skill wording clarifications (PRs against SKILL.md files)
   - Default model/effort tuning (PRs against frontmatter)
   - New skills if a pattern of 5+ ad-hoc `/task` requests suggests one
   - Deprecation of unused skills (never called, or 100% failure rate)
6. All proposals are PRs with a written rationale. You approve or reject.

---

## 8. Self-improvement

The distinction: **self-evaluation** tells the system *whether it did well*. **Self-improvement** tells the system *what to change so it does better next time.*

### 8.1 Signals (what the system watches)

| Signal | Source | Used by |
|---|---|---|
| Job succeeded/failed | Postgres `jobs.status` | escalation, retrospective |
| Job cancelled by user | Postgres + cancel event | retrospective (indicates frustration) |
| User rating 1-5 | `/rate <job_id> <N>` Telegram command | retrospective |
| Quality gate passed/failed | audit log event `quality_gate` | skill-level escalation |
| Cost per unit of work | `job_events.cost_usd` | auto-tuning |
| Review job outcome (LGTM/changes/blocker) | audit log event `review` | escalation, retrospective |
| Repeated error pattern in audit logs | regex over `tool_result` where `is_error=true` | self-diagnose trigger |
| Healthcheck failure for a project | `projects.last_healthy_at` stale | self-diagnose trigger |
| Event trigger: 2 failures in same skill in 10 min | in-memory counter in runner | self-diagnose enqueue |

### 8.2 Action taxonomy (what "improvement" looks like)

| Action | Risk | Mechanism | Approval |
|---|---|---|---|
| Append a gotcha to `GOTCHAS.md` | none | In-session during a failure | Auto |
| Append a debug note to `DEBUG.md` | none | In-session after a fix | Auto |
| Reword a SKILL.md's instructions for clarity | low | PR from `review-and-improve` | Auto-merge after `code-review` sub-agent LGTM |
| Change a skill's default model/effort | low-medium | PR | Manual approval via Telegram |
| Add a new skill | medium | PR via `new-skill` | Manual approval |
| Patch a project | medium | PR to project repo via `app-patch` | Manual approval (you merge) |
| Patch server code | high | PR via `server-patch` | Manual approval + `code-review` sub-agent must LGTM first |
| Add a new sub-agent / hook | high | PR via `server-patch` | Manual approval |
| Delete a project or skill | high | PR with `review-and-improve` rationale | Manual approval + confirmation DM |

The rule: **auto-apply only when the change is isolated to documentation files (skill GOTCHAS/DEBUG/PATTERNS).** Anything that touches executable code, default configs, or the skill *interface* is a PR.

### 8.3 Triggers (when improvement loops run)

| Trigger | Frequency | Job it enqueues |
|---|---|---|
| Skill session → failure during run | Inline | In-session append to GOTCHAS.md |
| 2 failures in same skill/10 min | Event-driven | `self-diagnose` |
| 3 consecutive cancel/reject on same skill | Event-driven | `review-and-improve` scoped to that skill |
| Daily at 23:00 | Cron | Quick anomaly check (script, not skill) — alerts on 2x deviation |
| Weekly Mon 08:00 | Cron | `review-and-improve` (light) — flags patterns, doesn't propose yet |
| Monthly 1st 00:00 | Cron | `review-and-improve` (full) — proposes PRs |
| On demand | `/task improve <area>` | Scoped `review-and-improve` |

### 8.4 Why this is a better design than the old self-improver

The old system tried to make improvement *autonomous and continuous*. That doesn't work yet because:
- Silent code changes by a loop are unreviewable in aggregate
- The approval UI (Telegram /approve) becomes another thing to maintain that's orthogonal to the work
- False-positive improvements ("the system thinks it improved but actually broke something") compound

The new design makes improvement **batched, explicit, and PR-driven**. You see every proposed change. You merge or reject. The system's job is *noticing* and *proposing*, not *deciding* and *applying*. This is also how senior engineers interact with improvement signals in real teams.

---

## 9. Self-management

What keeps the system alive with minimal intervention.

### 9.1 Process supervision

- launchd `KeepAlive=true` for each of runner/web/bot/caddy/cloudflared — auto-restart on crash
- Project service processes (type=`service` or `api`) also have individual launchd plists with KeepAlive=true
- Install location: `~/Library/Application Support/ai-server/` — avoids macOS Full Disk Access rule that broke your old launchd setup in `~/Documents`

### 9.2 Healthchecks

Two kinds, both running every 5 minutes:

- **Server healthcheck**: does `curl localhost:8080/health` return 200? does `redis-cli ping` work? does `pg_isready` succeed? If any fails → Telegram alert + trigger `self-diagnose` if repeated 3x in a row
- **Per-project healthcheck** (the `healthcheck-all` skill — pure script, no LLM): for each project with `healthcheck` set in manifest, hit `http://localhost:<port><healthcheck>`. Update `projects.last_healthy_at`. If fails 3x in a row → Telegram alert + enqueue `self-diagnose` with the project slug

### 9.3 Resource management

- **Daily Anthropic spend cap**: runner queries usage API hourly; at 80% of daily cap → Telegram warning; at 100% → pause job queue (jobs pile up; resume at midnight or manually with `/resume`)
- **Per-session budget** (`max_budget_usd`): SDK-enforced; session aborts if exceeded
- **Log rotation**: `server-upkeep` runs daily; rotates files >100MB; keeps 30 days
- **Audit log retention**: keep last 12 months; archive older to `volumes/audit_log/archive/<year>-<month>.tar.gz`
- **Database maintenance**: `server-upkeep` runs `VACUUM` weekly, checks disk use, archives `jobs` rows older than 90 days to a `jobs_archive` table
- **Backup**: `backup` skill runs nightly at 04:00; `pg_dump | gzip` + `tar -czf projects.tar.gz projects/`; writes to `~/backups/<YYYY-MM-DD>/`; optionally rsyncs to an off-site target if one is configured

### 9.4 Self-diagnose flow

When triggered (2 failures in same skill, healthcheck failure, or manual `/task diagnose`):

1. Enqueue a `self-diagnose` job with payload `{trigger: "healthcheck_fail", target: "market-tracker"}` or similar
2. Runner picks it up; cwd = server root
3. Claude (Opus 4.7 / high) reads:
   - Last 30 audit log entries for the target
   - Relevant service's logs (`volumes/logs/<service>.err.log`)
   - DB state (pending jobs, recent failures)
   - Healthcheck history
   - Relevant module's `.context/`
4. Outputs a structured diagnosis: symptom → root cause → proposed fix (with risk level)
5. Low-risk fix (config change, restart a service, clear a lock file): applies directly, verifies, reports
6. High-risk fix (code change): opens a PR via `app-patch` or `server-patch`, Telegrams you with a summary + PR link
7. Writes findings to `<module>/.context/skills/DEBUG.md` regardless of action taken

This replaces `src/meta/diagnostics.py` from the old system. It's smaller, clearer, and triggered *on-demand*, not in a hot loop.

---

## 10. Self-expansion

How the system grows itself.

### 10.1 New projects (`new-project` skill)

Covered in depth in the prior redesign doc — quick recap:

1. You say `/task new project: NBA scores widget, polls ESPN every 10 min, dark-mode dashboard`
2. Skill asks clarifying Qs if needed (stack? vanilla/React?)
3. Picks next port from `projects/_ports.yml`
4. Creates `projects/<slug>/` with scaffolded code, `manifest.yml`, `CLAUDE.md`, `.context/`
5. Runs `scripts/register-project.sh <slug>` which:
   - Generates Caddyfile snippet
   - Installs launchd plist if service-type
   - Reloads Caddy
   - Inserts row in `projects` table
6. Initializes a new GitHub repo (separate-repo-per-project per your choice)
7. Commits, pushes
8. Waits for healthcheck
9. Replies with the public URL

### 10.2 New skills (`new-skill` skill — the meta-work)

This is the self-expansion of the brain.

1. You say `/task new skill: every morning summarize overnight changes in the S&P 500`
2. `new-skill` analyzes the description:
   - What's the trigger? (scheduled | ad-hoc | event-driven)
   - What are the inputs?
   - What tools are needed?
   - What's the output shape?
   - What model/effort fits?
3. Drafts `skills/<slug>/SKILL.md` with frontmatter + procedure + quality gate
4. Runs `code-review` sub-agent on the draft with plan mode
5. If LGTM: opens a PR (or auto-merges if you pre-approved auto-merge for skill additions)
6. If the skill has a schedule, inserts a Schedule row
7. Appends to `.context/SKILLS_REGISTRY.md`
8. Replies with the skill's name and how to trigger it

First-order self-expansion. The system doesn't invent capabilities — you describe them. But it *packages* them into reusable skills that persist, get tuned via retrospectives, and become part of the library.

### 10.3 Server patches (`server-patch` skill)

The highest-risk expansion: modifying the server's own code.

**Hard rules**:
- Always runs in `plan` mode first; plan is output as a `text` block
- Plan is reviewed by a `code-review` sub-agent (Opus 4.7 / high, plan mode, read-only)
- If review says `blocker`: abort, Telegram you with details
- If review says `changes-requested`: remediate, re-review (max 2 cycles)
- If review says `LGTM`: opens a PR against `ai-server` repo, Telegram you with link
- **Never auto-merges server PRs.** Full stop. You merge manually after eyeballing the diff.

The `server-patch` skill is also what `self-diagnose` invokes when it determines the fix is in server code. This keeps the one careful pathway for server mutations.

### 10.4 What the system *cannot* do autonomously

Explicit ceilings:
- Can't delete a project (proposes, you confirm via Telegram Y/N)
- Can't delete a skill (same)
- Can't deploy to production environments outside your Mac Mini (no AWS, no Heroku, nothing cloud)
- Can't publish anything with your name on it to social media / blog / etc.
- Can't send emails from your account
- Can't charge anything
- Can't modify the `.context/PROTOCOL.md` file itself (proposes PRs like anything else)
- Can't modify its own authorization list (TELEGRAM_ALLOWED_CHAT_IDS is config-only, not data)

---

## 11. Hooks, sub-agents, and custom MCP tools

### 11.1 Agent SDK hooks we wire up

- **PreToolUse(Bash)**: match against a dangerous-command allowlist; block `rm -rf /`, `curl ... | sh` from untrusted domains, writes outside cwd. Log to audit.
- **PreToolUse(Write, Edit)**: assert path is within `cwd` (runner-scoped) unless skill explicitly declares write-outside paths (e.g., `new-project` declares it can write anywhere in `projects/`). Log to audit.
- **PostToolUse(*)**: always log result summary + error flag to audit. (Primary audit capture path is via message iteration; hooks are belt-and-suspenders.)
- **SessionStart**: load last N audit entries for scope (project or server); append as synthetic context block (implemented in runner, not as SDK hook if Python SDK hooks are shell-only on current version).
- **SessionEnd**: verify write-back; trigger follow-up session if needed; write `.summary.md`.

### 11.2 Sub-agents (sessions spawned by other sessions)

Not every skill uses sub-agents. The patterns where they matter:

| Parent skill | Sub-agent | Why |
|---|---|---|
| `research-deep` | parallel `research-report` sub-agents on different angles | Faster; avoids one huge context window |
| `new-project` | `code-review` after scaffold | Sanity-check before committing |
| `new-skill` | `code-review` on the new SKILL.md | Ensure it's coherent |
| `app-patch` | `code-review` on the diff | Catch regressions |
| `server-patch` | `code-review` on the diff (mandatory) | No server changes without review |
| `review-and-improve` | multiple `app-patch` or `new-skill` sub-agents for each proposed PR | Parallelize proposal generation |
| `self-diagnose` | `app-patch` or `server-patch` for the fix | Keep the single fix pathway consistent |

Each sub-agent runs as its own `ClaudeSDKClient` session, gets its own audit log file (`<parent_id>.sub.<n>.jsonl`), its own cost accounting. The parent's summary rolls up child costs.

### 11.3 In-process custom MCP tools

Built with `create_sdk_mcp_server()`. Run in the runner process; no separate server.

| MCP server | Tools | Used by |
|---|---|---|
| `projects` | `list`, `get(slug)`, `restart(slug)`, `manifest(slug)`, `logs(slug, n)` | `self-diagnose`, `app-patch`, `review-and-improve` |
| `audit` | `read_recent(n, filter)`, `read_summary(job_id)`, `find_failures(skill, since)` | `self-diagnose`, `review-and-improve` |
| `telegram` | `send(chat_id, text)` | `notify`, any skill that Telegrams mid-run |
| `dispatch` | `enqueue(kind, description, payload)` | parent → child sub-agent delegation |

Don't build these until a skill needs them. Built-in tools (Read/Write/Edit/Bash/Glob/Grep/WebSearch/WebFetch/AskUserQuestion) cover ~90% of what skills need.

---

## 12. Key invariants

Rules that hold regardless of what Claude does. Enforced in code.

| ID | Invariant | Where enforced |
|---|---|---|
| INV-1 | No session runs without a resolved model, effort, and permission_mode | `runner/session.py:_build_options` |
| INV-2 | Every job writes at least one `job_started` and one terminal event to audit log | `runner/main.py:_process_job` |
| INV-3 | Every session has a `max_budget_usd` cap (skill or server default) | `runner/session.py:_build_options` |
| INV-4 | Server code changes never auto-merge | `server-patch` SKILL.md + PR gate |
| INV-5 | Write-back verification runs after every session that modified code | `runner/main.py` post-session hook |
| INV-6 | Only whitelisted chat IDs can submit jobs via Telegram | `gateway/telegram_bot.py:_guard` |
| INV-7 | Only authenticated web requests can submit jobs | `gateway/web.py:_check_auth` |
| INV-8 | Interrupt requests are honored within 2 seconds | `runner/main.py:_cancel_listener` |
| INV-9 | Job status transitions are valid (queued→running→terminal only) | `models.py` + `_finish_job` |
| INV-10 | Skills in `plan` mode cannot write files | SDK-level; `permission_mode="plan"` |
| INV-11 | Audit logs are append-only | filesystem O_APPEND in `audit_log.append` |
| INV-12 | Daily spend cap pauses queue at 100% | runner budget check loop |
| INV-13 | `server-patch` always requires a passing `code-review` sub-agent | `server-patch` SKILL.md + runner post-hook |
| INV-14 | Project slugs are unique; port allocations never reused | `registry/manifest.py:validate` + `projects/_ports.yml` |

---

## 13. What this explicitly is NOT (bounded non-goals)

To keep the system from sprawling, stating what we're not going to try:

- **No agent marketplace / plugin ecosystem.** Skills are yours; they live in your repo.
- **No vector database.** Past system had pgvector for semantic memory; we've seen it's unnecessary. Audit log + skills + git history is enough.
- **No LLM-based routing for simple cases.** Keyword rules beat Haiku classification for the known skill set.
- **No custom evaluator/decision-engine architecture.** Quality gates inside skills + targeted review sub-agents + monthly retrospective is the whole eval story.
- **No cross-provider routing.** Anthropic only. If Anthropic is down, jobs queue; they don't fail over to GPT.
- **No real-time collaborative editing, multi-user accounts, or billing system.** Single-tenant.
- **No fine-tuning / custom models.** Use what Anthropic ships.
- **No "agent talks to agent" social fabric.** Sub-agents are called by parents, return to parents. No arbitrary mesh.

---

## 14. MVP scope vs full system

Tempting to build everything. Better to ship in layers and learn.

### Phase 1 — Foundation (3-4 days)
- Directory layout at `~/Library/Application Support/ai-server/`
- Postgres + Redis (reuse old installs)
- 3 tables, 1 Alembic migration
- Runner process (job_loop, scheduler_loop, cancel_listener) with Agent SDK integration
- Web gateway (FastAPI, `/api/jobs`, basic dashboard)
- Telegram bot (6 commands)
- launchd plists
- Server-level `CLAUDE.md`, `SERVER.md`, `.context/SYSTEM.md`, `.context/PROTOCOL.md` (copied from old repo)
- Skills directory seeded with just `chat` and `route`

**Done =** You can `/task <anything>`, the runner spawns a generic Claude session with the full tool set and acceptEdits permission, and you get a result DM'd back. No specialized skills yet. No projects yet.

### Phase 2 — First real skill (1 day)
- `research-report` SKILL.md
- Its output directory (`projects/research/`) with its own `.context/`

**Done =** `/task research the 2026 NBA trade deadline` produces a real markdown file, committed, and DMs you the TL;DR.

### Phase 3 — Domain + hosting (2-3 days)
- Buy domain on Cloudflare
- Named Cloudflare Tunnel with wildcard DNS
- Caddy installed + main Caddyfile
- `scripts/register-project.sh`
- `project-healthcheck-all` script + cron
- Migrate `baseball_bingo` (static) to `projects/bingo/` + register
- Migrate `market-tracker` (service) + register

**Done =** `bingo.yourdomain.com` serves from your Mac, `market-tracker.yourdomain.com` too. Healthchecks every 5 min. Public URLs stable across restarts.

### Phase 4 — The expansion skills (3-4 days)
- `new-project` SKILL.md + templates for static/service/api
- `app-patch` SKILL.md
- `new-skill` SKILL.md
- `code-review` SKILL.md (used by others, not directly user-triggered)
- `self-diagnose` SKILL.md
- `notify` MCP server
- `dispatch` MCP server (for sub-agents)

**Done =** Full autonomous project lifecycle: you say "build X", it builds, hosts, and opens the URL. Fix requests work. Skill library is self-expanding (within review gates).

### Phase 5 — Operations skills (1-2 days)
- `server-upkeep` SKILL.md + cron
- `healthcheck-all` script (per-project healthchecks)
- `backup` SKILL.md + cron
- `server-patch` SKILL.md (with PR gate)
- `review-and-improve` SKILL.md + monthly cron

**Done =** The system maintains itself. You wake up to a Telegram saying "disk at 70%, log rotation deferred one day, 3 failed healthchecks yesterday — diagnosed and fixed 2, the third is an upstream API outage." Monthly PRs show up proposing skill improvements.

### Phase 6 — Polish (ongoing)
- Fill in remaining skills: `research-deep`, `idea-generation`, `project-update-poll`, `restore`
- Add Cloudflare Access in front of dashboard for SSO
- Tune default model/effort settings per the auto-tuning data
- Whatever else you've learned you want

**Total realistic timeline to Phase 5**: 10-14 focused evenings.

---

## 15. Open design decisions — your call before I build

1. **Domain suggestion**: you mentioned Cloudflare registration. Need a name. Suggestions like `chris.sh`, `piserchia.dev`, `<your-initials>.xyz` — short is best. Want me to check availability on a couple you like?

2. **Separate repos per project**: confirmed from last round. The server repo (`ai-server`) gitignores `projects/*/`. Each project gets its own GitHub repo, cloned into `projects/<slug>/`. The `new-project` skill creates the new repo via `gh repo create`. You need the `gh` CLI installed and authenticated.

3. **Anthropic API key & daily cap**: I'll default to $5/day. You can override per-session or per-day. Confirm the default feels right.

4. **User ratings**: do you want a `/rate <job_id> <1-5>` command? It's a strong signal for auto-tuning but optional if you prefer fewer commands.

5. **Review-gate policy for skills vs server code**: my default is "skills auto-merge if `code-review` LGTM, server code always manual-merge." Are you OK with that, or do you want skills to also require manual merge?

6. **Default response language**: currently everything English. Just checking.

7. **Opus 4.7 as the server default**: I propose Sonnet 4.6 as the *global default* (overridden per-skill). Is that right, or do you want everything defaulting to Opus 4.7 even if pricier?

---

## 16. What this design buys you

Concrete promises:

- **You can ignore the system for a week** and it keeps running. Healthchecks catch issues, `self-diagnose` fixes the easy ones, Telegram alerts you on the hard ones.
- **You can come back to a project after 3 months** and a new Claude session has full context in under 30 seconds (CLAUDE.md → CONTEXT.md → recent audit logs).
- **You can ask it to build things and trust the outputs** because `code-review` sub-agents check diffs, write-back is enforced, and `server-patch` never ships silently.
- **You don't pay for what you don't need** — Haiku for routing, Sonnet for 80% of work, Opus 4.7 only when the task earns it.
- **You can add capabilities without writing code** — describe a workflow in plain English, `new-skill` packages it as reusable data.
- **The system tells you how to tune it** — monthly retrospectives, PR-driven suggestions, you approve or reject.
- **Nothing important happens without your sign-off.** No server mutations, no destructive operations, no spending sprees — all gated.

---

*This is the full shape. Push back on anything that feels wrong, ask for more depth on any piece, and once you're satisfied I'll tear down the old system and build Phase 1 against this spec.*
