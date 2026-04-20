# ai-server: Full Evaluation

> **Audience**: Chris (owner) and future Claude sessions reviewing the repo's
> trajectory.
> **Date**: 2026-04-18
> **Scope**: goals & how they're pursued, a theoretical model of "perfect
> Claude context injection", comparison of the current repo against that
> model, and concrete feature recommendations ordered by ROI.
> **Author**: Claude Opus 4.7, after cloning the repo at commit `a399cc7`
> and reading `src/`, `skills/`, `.context/`, `docs/`, `tests/`.

---

## Implementation status (live)

As recommendations are implemented they're marked here with commit SHA and
date. Update this section when a recommendation's work lands.

Numbering here corresponds to § 7 of this document. Priority ordering (from
§ 8) is: 1 → 5 → 3 → 10 → 2 for the first five (by § 7 numbering).

| § 7 Rec | Priority | Title | Status | Commit | Date |
|---------|----------|-------|--------|--------|------|
| 1 | P1 | Learning extractor post-session hook | **SHIPPED** | `542334c` | 2026-04-18 |
| 2 | — | Audit-log-derived context consumption signal | **SHIPPED** | `25b12bd` | 2026-04-19 |
| 3 | P1 | Seed module `skills/` dirs | **SHIPPED** | `adc1cbf` | 2026-04-18 |
| 4 | — | Graph-walked context injection | **SHIPPED** | `0421f38` | 2026-04-19 |
| 5 | P2 | `context_files` adoption sweep | **SHIPPED** | `599e577` | 2026-04-18 |
| 6 | — | Project-level PROTOCOL | **SHIPPED** | `6cffb19` | 2026-04-19 |
| 7 | — | Stale-context warnings in retrospective | **SHIPPED** | _pending_ | 2026-04-19 |
| 8 | — | Budget accounting | planned | — | — |
| 9 | — | Audit log index | planned | — | — |
| 10 | P1 | Proposal-applied tracking | **SHIPPED** | `bbe2bf6` | 2026-04-18 |
| 11 | — | Fix `test_review.py` collection errors | **RESOLVED (non-issue)** | `542334c` | 2026-04-18 |
| 12 | — | Autoregister projects in `PROJECTS_REGISTRY.md` | planned | — | — |
| 13 | — | `_writeback` "why" quality gate | planned | — | — |
| 14 | — | Chunk-level doc retrieval | planned | — | — |
| 15 | — | Tool-use-aware code review | planned | — | — |

---

## 1. What the repo is trying to do

ai-server is a **single-tenant personal assistant server** that runs on a
Mac Mini, accepts natural-language requests via Telegram or web, executes
them through the Claude Agent SDK on subscription auth, hosts the resulting
projects on `*.chrispiserchia.com`, and self-manages / self-heals / self-
improves over time. The anchoring document (`MISSION.md`) explicitly frames
it as an **autopoietic system**: the server should maintain, debug, extend,
and improve itself and its project catalog from a modular level, so that
efficiency and effectiveness compound without constant human intervention.

The key architectural choice that makes this tractable is **treating skills
as data**. Each `skills/<n>/SKILL.md` is YAML frontmatter (model, effort,
tools, escalation rules) plus a markdown body that becomes the Claude system
prompt. Adding a new capability doesn't require a deploy — it's a directory
with a file. The runner reads frontmatter, loads the body as the system
prompt, resolves a working directory, spins up a Claude SDK session. That's
the whole execution model.

The second key choice is **documentation as first-class artifact**. The
repo has a five-tier doc hierarchy: `CLAUDE.md` (root directive auto-loaded
by every session) → `.context/SYSTEM.md` (module graph + invariants) →
`.context/modules/<x>/CONTEXT.md` (per-module state) →
`.context/modules/<x>/skills/{GOTCHAS,PATTERNS,DEBUG}.md` (institutional
knowledge) → `volumes/audit_log/<job_id>.jsonl` (per-job evidence).
Every session that modifies code is supposed to write back to this
hierarchy per `.context/PROTOCOL.md`.

## 2. How the repo goes about its goals

### 2.1 The thirteen objectives and their instruments

From `MISSION.md` §§ A–M, the system binds each objective to specific
code or config. A condensed reading:

| Objective | Primary instrument |
|-----------|-------------------|
| A. Continuous personal-assistant behavior | 3 launchd-supervised processes (runner/web/bot) + auto-restart |
| B. Scheduled research/polling/upkeep | `schedules` Postgres table + `_scheduler_loop` + cron-triggered skill jobs |
| C. App creation + deployment | `new-project` skill scaffolds from description → `scripts/register-project.sh` wires to Caddy + launchd + DB |
| D. Multi-project hosting, one domain | Cloudflare named tunnel → Caddy reverse proxy → `Caddyfile.d/*.conf` per project |
| E. Idea generation | `idea-generation` skill + `projects/ideas/history.jsonl` dedup log |
| F. Self-management | `scripts/healthcheck-all.sh` every 5 min + `server-upkeep` skill daily + `backup` nightly + `quota.py` auto-pause |
| G. Self-debugging | `self-diagnose` skill (Opus 4.7 / high) + event trigger on 2 failures in 10 min |
| H. Self-improvement | `jobs` table tracks `resolved_skill`/`resolved_model`/`resolved_effort`/`user_rating`/`review_outcome` + `review-and-improve` skill queries via `retrospective.py` and proposes PRs |
| I. Self-expansion | `new-skill` (meta-skill) + `new-project` + `app-patch` + `server-patch` (PR-gated) |
| J. Smart model selection | SKILL.md frontmatter per skill + `router.py` for coding-intent routing + flag overrides + escalation.on_failure |
| K. Subscription economics | Bundled Claude Code CLI (no API key) + runner startup guard + `MAX_CONCURRENT_JOBS=2` |
| L. Documentation that compounds | The 5-tier hierarchy; `_writeback` auto-spawn hook; `scripts/lint_docs.py` enforcement |
| M. Safety ceilings | Server-patch always PR-gated; explicit INV-list in SYSTEM.md; PROTOCOL.md immutable |

### 2.2 The runtime shape

- **One runner process, four async tasks**: `_job_loop` (BLPOP from Redis queue, run via `session.run_session`), `_scheduler_loop` (every 30s, promote due schedules to queued jobs), `_cancel_listener` (subscribe to `jobs:cancel`, interrupt matching sessions), `event_loop` (every 60s, check for repeated failures / unhealthy projects / idle queue → auto-enqueue `self-diagnose` or `review-and-improve`).
- **Session construction in `runner/session.py:_build_options`** is where all policy concentrates: system prompt = context-aware server directive + skill body; model/effort come from skill frontmatter with payload override precedence; MCP servers injected based on skill name or tag; `setting_sources=["project"]` so the SDK auto-loads the project's `CLAUDE.md` from `cwd`.
- **One job → one audit log file**: `volumes/audit_log/<job_id>.jsonl` is append-only, grep-friendly, survives process crashes. Plus a `<job_id>.summary.md` one-paragraph record written at completion.
- **Escalation is one-level, guarded**: if a skill's frontmatter declares `escalation.on_failure: {model: X, effort: Y}` and the job fails, `_maybe_escalate` enqueues a retry with the escalated config. Payload flag `escalated_from` prevents loops.
- **Write-back verification**: after every successful non-chat job, `_verify_writeback` runs `git status --porcelain --untracked-files=all` in cwd; if non-doc files changed without CHANGELOG touched, it enqueues a `_writeback` child job. Non-fatal if the check itself fails.
- **Code review is a sub-agent**, not a separate job kind: `review.run_code_review` fires after sessions scoped to `{new-project, app-patch, server-patch}`, runs Opus 4.7 / high / plan mode on the diff, parses the first line for `LGTM|CHANGES|BLOCKER`, stamps `jobs.review_outcome`.

### 2.3 The learning loop (on paper)

1. Each job records `resolved_skill`, `resolved_model`, `resolved_effort`, `user_rating` (from `/rate`), `review_outcome` (from sub-agent).
2. `retrospective.skill_performance()` rolls these up by `(skill, model, effort)`: success rate, avg latency, avg rating, LGTM rate.
3. `review-and-improve` skill runs (scheduled weekly + event-triggered when queue idle > 24h), queries retrospective, proposes tuning PRs (`server-patch` for default changes, `new-skill`/`app-patch` PRs for skill-body improvements).
4. All proposals go through normal PR review. Skills auto-merge on code-review LGTM; server code always manual-merge.

### 2.4 What's been built vs planned

All six phases shipped. Measured from commit `a399cc7`:

- **Python source**: 3,671 LOC across 24 modules in `src/`
- **Bash scripts**: 930 LOC across 10 scripts in `scripts/`
- **Docs**: 6,458 lines across `docs/` + `.context/` (excluding skills)
- **Skills**: 16 skills, 2,835 lines of SKILL.md content
- **Tests**: 694 LOC across 5 pytest files; doc linter wired into pytest
- **Modules with `.context/modules/<x>/` docs**: 5 (db, gateway, hosting, registry, runner)
- **Projects hosted**: 2 (baseball-bingo static, market-tracker service); 2 server-managed content projects (research, ideas)

The doc linter (`scripts/lint_docs.py`) currently reports all clean: every
skill is in `SKILLS_REGISTRY.md`, every project in `PROJECTS_REGISTRY.md`,
every `src/runner/*.py` in the runner CONTEXT, every phase-plan status
matches SYSTEM.md. That's a strong signal for documentation integrity as of
this audit.

---

## 3. What "perfect Claude context injection" would look like

Before comparing, it's worth establishing what we're measuring against. If
we set aside implementation constraints and ask "what would an ideal system
for giving Claude the right context at the right time do?", the answer has
roughly seven properties. They cluster into three groups: retrieval,
compression, and feedback.

### 3.1 Retrieval (getting the right bytes into the window)

**R1. Task-relevance-driven retrieval, not static file lists.** A skill
shouldn't declare "read these five files" — it should declare "here's what
I'm trying to accomplish; pull context that matches." The ideal system
treats the skill's procedure, the user's job description, and the current
cwd as a query, then retrieves the k most-relevant files/sections using
semantic similarity over the `.context/` + `docs/` corpus. Static file
lists are a special case (pin these always). This preserves human control
but lets the system find things humans forgot to link.

**R2. Just-in-time sub-document retrieval.** Whole-file reads are wasteful
when you only need two sections. Perfect context would index docs
section-by-section (the headings you already write are natural chunk
boundaries) and pull relevant sections rather than whole files. For docs
like `docs/PHASE_4_PLAN.md` at 1,135 lines, this matters: a skill rarely
needs the full plan, it needs the "File-by-file plan → specific file"
subsection.

**R3. Graph-walked context.** If a skill modifies `src/runner/session.py`,
the ideal system doesn't only inject that module's CONTEXT. It walks the
dependency graph declared in SYSTEM.md and pulls CONTEXT for every
downstream module that imports it (so the session knows what it'll break).
Currently SYSTEM.md declares these edges but nothing uses them at
retrieval time.

### 3.2 Compression (fitting into the budget)

**C1. Budget-aware prompt construction.** The system should know, for each
model/effort combo, how many tokens of context it can afford to inject
without forcing later compaction. It should then rank retrieved chunks by
marginal information value and pack until the budget fills. This means
small highly-relevant snippets can displace large borderline-relevant
files.

**C2. Layered context with on-demand deep-dive.** The preamble injects a
"context map" (titles + one-line summaries of the top 30 relevant
artifacts); the actual content of any artifact is fetched via a tool call
when the session decides it needs the detail. This matches how humans work
with documentation: you scan an index, drill into specifics. It also
means the session can iterate — if first pass was insufficient, it can
pull more.

### 3.3 Feedback (context gets better over time)

**F1. Learnings extracted automatically from audit logs.** After every
job, a lightweight pass (Haiku) reads the audit log and the final summary
and decides: did we discover a new gotcha? a new pattern? a debug hint?
If yes, emit a structured proposal to append to `GOTCHAS.md` / `PATTERNS.md`
/ `DEBUG.md` for the right module. Humans (or `code-review`) gate the
append. The result: institutional knowledge grows without anyone manually
curating it.

**F2. Context quality as a measurable signal.** Every session reports
which context artifacts it actually used (via tool-call logs or explicit
reflection). Artifacts that never get consulted get demoted in retrieval
ranking. Artifacts that get consulted and were followed by a successful
outcome get promoted. Effectively: Bayesian updating of the "usefulness"
weight of each piece of context.

**F3. Feedback shapes future retrieval.** The retrieval layer uses the
F2 weights. Over time, a skill that runs 100 times learns which ten
sections of the corpus it actually depends on; those get auto-populated
as the skill's effective `context_files`. Humans can override. This is
the loop that lets "documentation compounds" actually mean something.

### 3.4 One more: the meta-loop

**M1. The context system critiques itself.** A scheduled skill (weekly or
monthly) treats the context corpus itself as a dataset: are there
CHANGELOG entries referencing files that no longer exist? Are there modules
whose CONTEXT.md hasn't changed in 30+ days while their source has? Are
there skills with zero runs that should be pruned? The output is a PR.
This is `review-and-improve` generalized to documentation.

---

## 4. How the current repo measures against that ideal

The honest read: the repo has **built the scaffolding for roughly 60-70% of
the ideal**, but has the **feedback loops on paper while skipping the
implementation**. Concretely:

### 4.1 Retrieval — partial credit

**R1 (task-relevance-driven retrieval)**: the `context_files` frontmatter
field exists and works — it appends "Read these files first" to the
session directive. But **only 2 of 16 skills use it**: `self-diagnose`
(lists `docs/Troubleshooting.md`) and `review-and-improve` (lists
`SKILLS_REGISTRY.md`, `SYSTEM.md`). Seven other skills reference specific
files in their SKILL.md body as prose instructions ("Read the project's
CLAUDE.md") — that still works because Claude follows the prose, but it
doesn't pre-load, it requires a Read tool call on each run, and the file
isn't in the system prompt when Claude is deciding whether to read it.

**R2 (sub-document retrieval)**: absent. When a skill declares
`context_files`, the session directive says "read these files first" — the
session does a Read on the whole file. No chunk-level granularity. For
small files this is fine; for docs like `PHASE_4_PLAN.md` (1,135 lines) or
`PROTOCOL.md` (225 lines), it's wasteful — but none of the current skills
actually reference those.

**R3 (graph-walked context)**: the module graph exists in `SYSTEM.md` as
a human-readable table. Nothing programmatically uses it. When a session
modifies `src/runner/session.py`, it does not automatically see
`.context/modules/gateway/CONTEXT.md` or any other downstream dependent.
The dependency graph is documentation, not machinery.

### 4.2 Compression — not yet addressed

**C1 (budget-aware construction)**: doesn't exist. The SKILL.md body is
appended to the server directive verbatim, regardless of model
(Sonnet's 200K vs Opus's 200K+ effective vs Haiku's 200K). There's no
accounting of how much of the budget is being consumed by static context,
and no dynamic ranking.

**C2 (layered context with on-demand deep-dive)**: doesn't exist
explicitly, but the tool-call model approximates it — skills declare
`required_tools: [Read, Glob, Grep]` and can walk the filesystem. What's
missing is the **index in the prompt** — the session has to use Glob to
discover what docs even exist. `INDEX.md` is the manually-maintained index,
but it's only read if the skill tells the session to read it.

### 4.3 Feedback — paper-only

**F1 (auto-extracted learnings)**: the PROTOCOL.md write-back defines
where learnings go (GOTCHAS.md / PATTERNS.md / DEBUG.md) and the session
is instructed to populate them. **In practice, only the `runner` module
has a `skills/PATTERNS.md`**. No GOTCHAS.md, no DEBUG.md. The other four
modules (db, gateway, hosting, registry) have no skills/ directory at all.
For 16 skills and dozens of jobs run during testing, exactly one
institutional-knowledge artifact has been created.

The reason is plain: write-back is manual, it's at the end of a long task,
and humans (including Claude) skimp on it when tired. The `_writeback`
auto-spawn catches missing CHANGELOG updates but doesn't synthesize
learnings — it tells Claude "you changed code without updating CHANGELOG,
go do that" which produces a mechanical entry, not genuine knowledge
extraction.

**F2 (context quality as signal)**: doesn't exist. No session reports
which files it actually read. The audit log records `tool_use` events so
in principle you could mine it for "files consulted", but no one does.
Retrieval has no feedback loop.

**F3 (feedback shapes retrieval)**: doesn't exist because F2 doesn't.

### 4.4 Meta-loop — partial

**M1 (context system self-critique)**: the doc linter (`scripts/lint_docs.py`)
catches structural inconsistency — skills not in registry, files not in
module CONTEXT, stale phase status. But it's an existence check, not a
quality check. It doesn't flag stale CONTEXT.md (where the code moved on
but docs didn't), orphaned files (docs referenced by nothing), or
doc-doc contradictions. `review-and-improve` could in principle do this,
but its current prompt focuses on skill-performance tuning, not doc
quality.

### 4.5 Summary grid

| Ideal property | Current state | Severity of gap |
|----------------|---------------|-----------------|
| R1 Task-relevance retrieval | Static `context_files`, 2/16 adoption | **Medium** |
| R2 Sub-document retrieval | Whole-file reads only | Low |
| R3 Graph-walked context | Graph exists, not used at runtime | **Medium** |
| C1 Budget-aware construction | Not implemented | Low (Opus windows are generous) |
| C2 Layered context + deep-dive | Approximated via tool calls | Low |
| F1 Auto-extracted learnings | 1 PATTERNS.md across 5 modules | **High** |
| F2 Context quality signal | Not implemented | **High** |
| F3 Retrieval improves over time | Not implemented | **High** |
| M1 Context self-critique | Existence-only via lint_docs | **Medium** |

The pattern is clear: **the system has solved the "write it down" problem
and left the "close the loop" problem for later**. That matches the build
order — it's cheaper and faster to establish a corpus than to make the
corpus self-curating, and you need a corpus before curation is useful.
But the autopoietic promise in MISSION.md requires the loops. Without
them, the system grows in breadth (more skills, more projects) without
growing in depth (better skills, better projects).

---

## 5. Specific strengths worth preserving

Before recommending changes, it's important to name what's genuinely good
and shouldn't be disturbed. Any future changes should respect these:

### 5.1 Skills-as-data

The SKILL.md format (frontmatter + body) is the single best decision in
the repo. It makes capabilities inspectable, diffable, reviewable (as PRs),
and addable without redeploy. The auto-merge-on-LGTM policy for skills (vs
manual merge for `src/`) is the right asymmetry — it keeps the high-churn
layer fluid while protecting the foundation.

### 5.2 Append-only audit logs as JSONL files

Putting audit logs in the filesystem as one JSONL per job (rather than a
DB table) is exactly right. Grep-friendly, diffable, immutable by
filesystem semantic, trivial to stream to Claude via Read. When future
sessions debug old jobs, `cat volumes/audit_log/<id>.jsonl` works without
setup.

### 5.3 Subscription-auth guard rails

The triple defense against `ANTHROPIC_API_KEY` (startup check in runner,
unset in bootstrap/run/launchd scripts, documented in CLAUDE.md and
MISSION.md) is the kind of paranoia that matches the cost dynamics. One
leaked env var on a 24/7 server could burn the month's budget overnight.

### 5.4 Invariants table with enforcement locations

`SYSTEM.md` § Invariants lists 14 hard rules with the specific file:line
that enforces each. This is what invariants are supposed to look like —
not aspirational rules but traceable commitments. Future refactors that
break an invariant become visible the moment someone edits the enforcing
code.

### 5.5 Phase plans with "what actually happened" sections

Every shipped phase plan (3, 4, 5, 6) has a "What actually happened"
section documenting deviations from the original plan. This is the
repo's most valuable documentation artifact — it captures intent vs
reality, which is what humans reading the repo months later need most.
The habit should be maintained for all future work.

### 5.6 Write-back auto-spawn

The `_verify_writeback` hook that auto-enqueues `_writeback` child jobs
when CHANGELOG wasn't touched is a good enforcement pattern — it catches
the most common failure mode (forgetting) without blocking the primary
session. The child-job-with-parent-link pattern (documented in
`.context/modules/runner/skills/PATTERNS.md`) is reusable for other
enforcement loops.

### 5.7 Doc linter as pytest

`scripts/lint_docs.py` running inside pytest means doc drift is treated
as a test failure, not a "would be nice to check" item. This is the
right posture — any tooling that isn't in CI doesn't get run.

---

## 6. Gaps ranked by marginal impact

Working from the 4.5 grid but weighting by how much each gap throttles the
autopoietic promise:

### 6.1 Top tier — these throttle compounding

**G1. Learnings don't extract themselves.** The write-back protocol says
"if you discovered something non-obvious, append to skills/\<module\>/GOTCHAS.md".
In practice, this happens rarely because (a) the primary session is at
end-of-turn and tired, (b) it has to decide what counts as non-obvious,
(c) even the `_writeback` auto-spawn only fixes CHANGELOG, not GOTCHAS.
After dozens of job runs, only one PATTERNS.md exists and zero GOTCHAS.md
exist.

**G2. No measurement of what context is actually helping.** Audit logs
record every tool use, so we can see which files sessions Read. No one
aggregates this. The corollary: there's no empirical basis for deciding
which `context_files` a skill should declare — you're guessing.

**G3. Retrospective queries exist but aren't fed back automatically.** The
`retrospective.py` module has `skill_performance()` returning rich rollups.
`review-and-improve` uses them. But nothing takes the output and updates
skill frontmatter. The loop exists from data → proposal; from proposal →
PR → merge exists; from merge → new-default being used exists. What
doesn't exist is a **closed check that proposals get applied**. You could
have `review-and-improve` propose the same change three months in a row
because the PR got ignored and no one notices.

### 6.2 Middle tier — these degrade quality over time

**G4. Dependency graph is documentation-only.** When you modify
`runner/session.py`, nothing surfaces the list of downstream modules
(`gateway.jobs`, `audit_log`, `registry.skills`) so you can reason about
impact. The graph sits in a markdown table. This is a modest cost per
change but compounds: new files get added without the graph being
updated (this already happened — `mcp_projects`, `mcp_dispatch`,
`retrospective`, `retention` all added in phases 4-6, all visible in
SYSTEM.md because humans remembered, but no tool enforces it).

**G5. Module `skills/` dirs are mostly empty.** Four of five modules
have no `skills/` subdirectory at all, meaning no place to accumulate
gotchas. The pattern from PROTOCOL.md expects them; the repo doesn't
create them until there's a finding. Failure mode: an agent with a
finding, no directory, no precedent, skips the write-up.

**G6. `context_files` adoption at 2/16.** Skills that reference
specific files in their prose (7/16 by my count) could move those to
`context_files` for zero cost and measurable efficiency gain — sessions
would have the file content in the prompt rather than needing a Read
call. Free improvement blocked only by under-utilization.

**G7. No project-level `.context/` governance.** Projects each have
their own `.context/CONTEXT.md` (per the registry), but there's no
protocol analogous to PROTOCOL.md at the project level. When `app-patch`
modifies `projects/market-tracker/`, the writeback verification runs but
writes to a project-level CHANGELOG that may or may not exist depending
on whether the project was scaffolded with one.

### 6.3 Lower tier — nice-to-haves

**G8. No budget accounting.** Session context is dropped in whole, no
count of tokens used by static context vs dynamic tool calls. For Opus
runs, context rarely fills, but for long `self-diagnose` jobs reading
200+ audit log lines, you can hit compaction.

**G9. Projects-registry governance is thin.** `PROJECTS_REGISTRY.md`
is hand-edited per the header comment. The `register-project.sh` script
inserts a DB row but doesn't update the registry markdown. This is
caught by the doc linter now, but the error surface is annoying — humans
forget, lint fails, humans patch, lint passes.

**G10. The `_writeback` auto-spawn is mechanical.** It triggers on
"code changed, CHANGELOG didn't" and fires off a Sonnet-low job that
writes a CHANGELOG entry. The entry quality is bounded by "what's in
`git diff --stat` + the parent summary". If the parent session didn't
articulate *why* in its summary, the `_writeback` job can't invent it.

**G11. `test_review.py` has collection errors** (or did in my sandbox —
might be env-specific). If real, tests aren't actually all passing, and
the review-code-path isn't being validated.

---

## 7. Feature recommendations

Ordered by **(impact on autopoiesis)/(implementation effort)**. Each has
a concrete specification so you can start without re-deriving the design.

### Rec 1 — "Learning extractor" post-session hook

**Problem solved**: G1, partially G2.
**Effort**: Small (~1 day). **Impact**: Very high.

After every non-chat, non-internal job completes, run a fourth async hook
(alongside write-back verification and post-review): a single-turn Haiku
session that reads the audit log for the just-completed job and the final
summary, and emits a structured JSON:

```json
{
  "had_learning": true,
  "module": "runner",
  "category": "GOTCHA",
  "title": "MCP tool args are dict, not kwargs",
  "content": "The @tool decorator wraps args in a single dict...",
  "evidence_job_id": "abc12345"
}
```

If `had_learning: true`, enqueue a child `_learning_apply` internal job
(new) that:
1. Reads the proposed learning
2. Checks whether `.context/modules/<module>/skills/<CATEGORY>.md` exists; creates if not
3. Appends the entry with a YYYY-MM-DD header and evidence job ID
4. Runs `code-review` sub-agent on the append
5. On LGTM, commits

This closes the learning-extraction loop with minimal token cost (Haiku
classification is cheap, only runs on jobs where classification says yes).

**Files**:
- New: `src/runner/learning.py` (the extractor)
- New: `skills/_learning_apply/SKILL.md`
- Modify: `src/runner/main.py` (add hook call in `_process_job`)
- New tests in `tests/test_learning.py`

### Rec 2 — Audit-log-derived context usefulness signal

**Problem solved**: G2, G3, G6.
**Effort**: Medium (~2-3 days). **Impact**: High over 3+ months.

Extend `retrospective.py` with a new rollup:

```python
async def context_consumption(
    since: datetime | None = None,
) -> list[ContextUsage]:
    """For each file path ever read by any session, return
    (skill, file_path, read_count, subsequent_success_rate,
    avg_rating_when_read)."""
```

Implementation: walk audit logs in the window, extract `tool_use` events
where `tool_name == "Read"`, group by (resolved_skill, file_path), join
against jobs table for status / rating.

Expose on `/api/retrospective/context` dashboard endpoint. Update
`review-and-improve` SKILL.md to query this and propose `context_files`
additions for skills where the same file is read in >50% of runs (cheap
win — that file should be pre-loaded).

**Files**:
- Modify: `src/runner/retrospective.py` (new function)
- Modify: `src/gateway/web.py` (new route)
- Modify: `skills/review-and-improve/SKILL.md` (consume new data)
- Add: dashboard tile in web UI

### Rec 3 — Module `skills/` dir auto-bootstrap

**Problem solved**: G5, makes G1 easier.
**Effort**: Tiny (~half-day). **Impact**: Low on its own, unlocks Rec 1.

Add `scripts/seed-module-skills.sh` that creates empty `GOTCHAS.md`,
`PATTERNS.md`, `DEBUG.md` in every module's `skills/` dir if missing.
Stub each with the format header so Claude sessions have a template to
append to. Add to bootstrap.sh and include a pytest check
(`test_doc_lint`) that every `.context/modules/<x>/skills/` directory
exists (empty is fine).

The goal is removing the "no directory → no findings" friction.

**Files**:
- New: `scripts/seed-module-skills.sh`
- Modify: `scripts/bootstrap.sh`
- Modify: `scripts/lint_docs.py` + `tests/test_doc_lint.py`

### Rec 4 — Graph-walked context injection

**Problem solved**: G4.
**Effort**: Medium (~2 days). **Impact**: Medium.

Parse the module graph from `SYSTEM.md` (it's a markdown table) at
runner startup into a `dict[module, list[module]]` dependency map. In
`_build_server_directive`, when the cwd implies a server-code session
and the job description or payload mentions modules, auto-append
"You're working in module X. It's depended on by [Y, Z]. Consider
reading their CONTEXT.md before changes."

Alternative form: generate the forward/reverse dependency graph from
actual imports (`ast.parse` each file in `src/`, collect `from src.X`
lines) and compare against declared graph. Emit a doc-lint warning
when imports don't match declarations.

This also gives you G-enforcement: the linter catches when someone adds
a new module dependency without updating SYSTEM.md.

**Files**:
- New: `src/context/module_graph.py` (parser + enforcer)
- Modify: `src/runner/session.py:_build_server_directive`
- Modify: `scripts/lint_docs.py` + `tests/test_doc_lint.py`

### Rec 5 — `context_files` adoption sweep

**Problem solved**: G6.
**Effort**: Tiny (~1-2 hours). **Impact**: Small but immediate.

For the 7 skills that reference specific files in prose, move those to
`context_files` frontmatter. Concrete targets based on current grep:

- `idea-generation`: `projects/ideas/history.jsonl`, `projects/ideas/README.md`
- `new-project`: `.context/PROJECTS_REGISTRY.md`, `projects/_ports.yml`, `projects/README.md`
- `new-skill`: `.context/SKILLS_REGISTRY.md`, `skills/README.md`
- `project-evaluate`: existing `CLAUDE.md`, `.context/CONTEXT.md`, `manifest.yml` if present
- `project-update-poll`: project's `manifest.yml`
- `research-deep`: `skills/research-report/SKILL.md` (references the base skill)
- `server-patch`: `.context/SYSTEM.md`, `.context/PROTOCOL.md`, relevant module CONTEXT

Pair this with Rec 2's data once it's running — adoption becomes data-driven.

**Files**: just edits to the 7 SKILL.md frontmatters.

### Rec 6 — Project-level PROTOCOL

**Problem solved**: G7.
**Effort**: Small (~half-day). **Impact**: Medium, avoids decay of project docs.

Create `.context/PROJECT_PROTOCOL.md` with the analogous write-back rules
for project-scoped sessions. Update `app-patch` and `new-project` SKILL.md
to reference it. Update `_build_server_directive` to point project-scoped
sessions at it.

The project-level `_writeback` hook (same module, different cwd) already
works — this just gives it the destination protocol.

**Files**:
- New: `.context/PROJECT_PROTOCOL.md`
- Modify: `skills/app-patch/SKILL.md`, `skills/new-project/SKILL.md`
- Modify: `src/runner/session.py:_build_server_directive`

### Rec 7 — Stale-context warnings in retrospective

**Problem solved**: M1 (existing) + G4 follow-through.
**Effort**: Small (~1 day). **Impact**: Medium.

Add to `review-and-improve` skill: check for `.context/modules/<x>/CONTEXT.md`
files whose mtime is more than 30 days older than the newest
`src/<x>/*.py` file's mtime. Check for `CHANGELOG.md` files with no
entries in 60+ days despite git log showing commits to their module in
the same window. Emit as retrospective findings.

This makes "documentation decay" a measurable, proposed-PR-level concern
rather than something you notice only when it bites.

**Files**:
- Modify: `src/runner/retrospective.py` (new function)
- Modify: `skills/review-and-improve/SKILL.md` (consume)

### Rec 8 — Budget accounting in session options

**Problem solved**: G8.
**Effort**: Medium (~1 day). **Impact**: Low for now, high if context sizes grow.

Track tokens consumed by static context (system prompt + context_files
bytes / ~4 chars/token estimate). Log into audit log as
`context_budget_used`. In `review-and-improve`, flag skills whose static
context > 30% of model budget for the Sonnet tier (where the window is
tightest). Propose slimming.

**Files**:
- Modify: `src/runner/session.py` (estimate + log)
- Modify: `src/runner/retrospective.py` (aggregate)

### Rec 9 — Audit log index

**Problem solved**: partial G2; general quality-of-life.
**Effort**: Small (~1 day). **Impact**: Medium for debugging.

Nightly job (add to `server-upkeep` or a new `reindex-audit` timer):
build `volumes/audit_log/INDEX.jsonl` with one line per job containing
`{job_id, skill, model, effort, status, user_rating, review_outcome,
error_first_line, keywords_in_summary}`. When `self-diagnose` runs on a
failure, it reads the index first to find similar past failures by keyword
or skill, then drills into specific audit logs. Cheap to maintain,
massive speedup for retrospective work.

**Files**:
- New: `scripts/reindex-audit.sh` or `src/runner/audit_index.py`
- Modify: `skills/self-diagnose/SKILL.md` (consume the index)
- Add launchd plist for nightly rebuild

### Rec 10 — Proposal-applied tracking

**Problem solved**: G3 (the gap in the existing feedback loop).
**Effort**: Small (~half-day). **Impact**: High for closing the loop.

Add a `proposals` table (or JSON column on review-and-improve job rows):

```
CREATE TABLE proposals (
  id UUID PRIMARY KEY,
  proposed_by_job_id UUID REFERENCES jobs(id),
  target_file TEXT,
  change_type TEXT,  -- 'default-model' / 'context-files' / 'frontmatter-tweak'
  proposed_at TIMESTAMP,
  applied_pr_url TEXT,
  applied_at TIMESTAMP,
  outcome TEXT  -- 'merged' / 'rejected' / 'pending' / 'superseded'
);
```

`review-and-improve` inserts rows when it proposes. A manual `/review
proposals` Telegram command lists pending. When a PR merges,
`server-patch` marks the row. When `review-and-improve` runs again, it
checks: did I propose this same thing last time? If yes and outcome is
'pending' or 'rejected', don't re-propose — note it in the summary as
"previously proposed, see proposal <id>".

Closes the infinite-proposal loop.

**Files**:
- Migration: new proposals table
- Modify: `skills/review-and-improve/SKILL.md` (read/write proposals)
- Modify: `skills/server-patch/SKILL.md` (mark proposal on merge)
- Bot: new `/proposals` command

### Rec 11 — Fix `test_review.py` collection errors

**Problem solved**: G11.
**Effort**: Trivial once reproduced. **Impact**: Correctness of CI signal.

My sandbox showed `tests/test_review.py` had collection errors. Worth
confirming on the real environment: `pipenv run pytest tests/test_review.py
-v`. If it fails, fix the imports / missing fixtures. If it passes in
your env, this was sandbox-specific and can be dropped.

### Rec 12 — Autoregister projects in `PROJECTS_REGISTRY.md`

**Problem solved**: G9.
**Effort**: Small (~2 hours). **Impact**: Low but closes a loop.

Modify `scripts/register-project.sh` to append to or update the markdown
table in `PROJECTS_REGISTRY.md`. A templated row from the manifest values.
Use a comment-delimited block for parsing:

```markdown
<!-- PROJECTS_AUTOGENERATED_START -->
| slug | type | subdomain | ... |
| baseball-bingo | static | bingo.chrispiserchia.com | ... |
<!-- PROJECTS_AUTOGENERATED_END -->
```

register-project regenerates the block between markers. Hand-editable text
lives outside the block.

**Files**:
- Modify: `scripts/register-project.sh`

### Rec 13 — "Why" quality gate for `_writeback`

**Problem solved**: G10.
**Effort**: Small. **Impact**: Medium for long-term doc quality.

Update `skills/_writeback/SKILL.md` to require that the final CHANGELOG
entry contains a non-empty "Why" section. If the parent job's summary is
too thin, the `_writeback` session should reconstruct reasoning by reading
the audit log tool-use events (what files it touched, in what order) and
articulate the likely why. This raises entry quality from "changed foo.py"
to "changed foo.py because the bar check was silently passing when it
should have returned False".

**Files**:
- Modify: `skills/_writeback/SKILL.md`

### Rec 14 — Chunk-level doc retrieval (longer-horizon)

**Problem solved**: R2, prerequisite for deeper retrieval work.
**Effort**: Large (~5-7 days). **Impact**: Medium; matters mostly as docs
grow past 10K lines.

Build a small index: for every markdown file in `.context/`, `docs/`,
`skills/`, split on H2 headings, embed each chunk with a local
sentence-transformer (no API cost), store in a sqlite-vss table. Add
an MCP tool `search_context(query) -> list[{file, section, snippet}]`
exposed to skills that opt into `needs-context-search` tag.

This is overkill for current doc size but lays the foundation for R1/R2
/R3 done properly.

**Files**:
- New module: `src/context/retrieval.py`
- New: sqlite-vss installation + embedding model
- New MCP server: `src/runner/mcp_context.py`
- Modify: relevant SKILL.mds to opt in

Flag as "nice to have, not yet" — the payoff only shows once the corpus is
big enough that static `context_files` stops scaling.

### Rec 15 — Proactive tool-use audit in code-review

**Problem solved**: sidebar — makes `code-review` outputs richer, improves F2.
**Effort**: Small (~1 day). **Impact**: Small, directional.

When `code-review` runs as sub-agent, also pass the parent job's audit log
as context. Reviewer sees not just the diff but what tools the parent used
to arrive at the diff (how many Reads, whether they Grepped before writing,
etc.). Output format adds an "Approach" section alongside LGTM/CHANGES/
BLOCKER where the reviewer comments on methodology.

This starts to capture process quality, not just output quality — feeding
back into F2 eventually.

**Files**:
- Modify: `src/runner/review.py` (pass audit log excerpts)
- Modify: `skills/code-review/SKILL.md` (prompt for approach critique)

---

## 8. Priority sequence

If I had to pick five to do first and in order:

1. **Rec 3** (bootstrap module `skills/` dirs) — trivial, removes friction for everything else
2. **Rec 5** (context_files sweep) — tiny effort, immediate token savings
3. **Rec 1** (learning extractor hook) — the single biggest loop to close
4. **Rec 10** (proposal tracking) — closes the feedback loop on retrospective proposals
5. **Rec 2** (context consumption signal) — data foundation for data-driven context

After those five, the autopoietic promise becomes real: the system would be
actively learning from its runs, tracking which context helps, closing the
proposal loop, and growing institutional knowledge automatically. Recs
4/6/7 are the next tier for structural hygiene. Recs 8/9/11/12/13 are
quality-of-life. Rec 14 is a capability upgrade for when doc volume grows
2-3x. Rec 15 is experimental.

---

## 9. Closing honesty

The repo is in notably good shape. The bones are right: skills-as-data,
PR-gated self-modification, append-only audit logs, explicit invariants,
context-aware directive construction. What's missing is the closing of
loops that the architecture makes possible but doesn't yet fire.

The risk to watch is the usual one with ambitious self-modifying systems:
breadth without depth. It's easier to add a 17th skill than to make the
16th skill materially better. The recommendations above bias toward
**depth work** — extracting signal from existing runs, closing feedback
loops, making retrieval data-driven — because that's what will make the
system substantively better over the next three months, not just bigger.

The five-recommendation sequence in § 8 is roughly 5-8 days of focused
work. If executed, the result would be a system where:

- Every job run produces structured learnings that accumulate in the right place
- Every skill's context budget is driven by what past runs actually consulted
- Every proposal tracks its fate, preventing infinite-proposal loops
- The doc corpus actively signals its own decay
- Future Claude sessions open the repo with markedly better per-skill orientation

That's what finishing the autopoietic promise looks like. Everything else
is polish.
