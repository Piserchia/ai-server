# Remaining recommendations — specs extracted from EVALUATION_2026-04-18.md § 7

These are the verbatim recommendation specs for the recs that were still
planned at handoff time. Priority order per § 8 of the evaluation doc:

**After Rec 10 + Rec 2**: do these roughly in numeric order, but feel free
to rearrange if dependencies become clear (e.g. Rec 9 "audit log index" might
speed up Rec 2's audit log walking, so doing 9 before 2 could make sense;
similarly 7 depends on conventions from 1, etc.).

Rec 11 is already resolved (non-issue). The full evaluation doc is at
`docs/EVALUATION_2026-04-18.md` — consult it for the gap taxonomy (§ 3)
and prioritization reasoning (§ 8).

---

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
