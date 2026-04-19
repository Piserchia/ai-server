# Rec 2 — Context consumption signal

**Problem solved**: G2, G3, G6 (see `docs/EVALUATION_2026-04-18.md` § 3 for the
gap taxonomy).
**Effort**: Medium (~2-3 days).
**Impact**: High over 3+ months.

## Goal

Teach `review-and-improve` what files are actually useful to skills. A
file that's read in >50% of a skill's runs should be pre-loaded via
`context_files` (zero-cost win); a file never read can be removed from
`context_files`.

## Implementation

### 1. New rollup in `src/runner/retrospective.py`

Add:

```python
async def context_consumption(
    since: datetime | None = None,
) -> list[ContextUsage]:
    """For each (skill, file_path) ever Read by any session, return
    read_count + subsequent success_rate + avg_rating_when_read.

    Walks audit logs in the window, extracts tool_use events where
    tool_name == "Read", groups by (resolved_skill, file_path), joins
    against jobs table for status / rating.
    """
```

Return a list of dataclasses/TypedDicts:

```python
@dataclass
class ContextUsage:
    skill: str
    file_path: str
    read_count: int
    success_rate: float   # fraction of reading jobs that completed successfully
    avg_rating: float | None   # None if no ratings exist
```

**Audit log walk pattern** (already used elsewhere in `retrospective.py` —
follow the existing style):

1. Read all `volumes/audit_log/*.jsonl` modified since `since`
2. Each line is a JSON event; filter for `{"kind": "tool_use", "tool_name": "Read", ...}`
3. Extract `input.file_path` (exact key depends on the tool-use schema —
   check an existing audit log line to confirm)
4. Group by `(resolved_skill, file_path)` — get `resolved_skill` from the
   jobs table keyed on `job_id` (which is the audit log filename without `.jsonl`)
5. Join jobs: count successes, compute avg rating across that skill's jobs
   that read that file

**Pure-function testable helpers** — break out the parsing logic so it's
unit-testable without DB:

```python
def parse_read_events(audit_log_lines: list[str]) -> list[tuple[str, str]]:
    """Pure. Parse audit log JSONL lines; return list of (job_id, file_path)
    for every Read tool_use event."""
```

### 2. New route in `src/gateway/web.py`

```
GET /api/retrospective/context?since=YYYY-MM-DD
  → JSON: [{skill, file_path, read_count, success_rate, avg_rating}, ...]
```

Follow the existing route pattern. Look at e.g. the `/api/retrospective/<rollup>`
routes already in `web.py` and mirror the style.

### 3. Update `skills/review-and-improve/SKILL.md`

Add a new "Context files audit" section (before the "Proposal tracking"
section added in Rec 10). Spec:

- Call `context_consumption(since=<review_window>)` or hit the API route
- For each `(skill, file_path)` pair where `read_count >= 5` AND the read
  rate exceeds 50% of that skill's runs in the window, propose a
  `change_type=context-files` addition to that skill's frontmatter
- Respect the Rec 10 dedup flow: check `find_recent_duplicate` first,
  then `insert_proposal` and include `Proposal-ID:` in the PR body
- For pairs with `read_count >= 5` AND read rate < 10%, propose REMOVAL
  from context_files (also `change_type=context-files`)

### 4. Dashboard tile (optional, not blocking)

Add a "Context consumption" tile to the web UI. If time allows.

## Files

- Modify: `src/runner/retrospective.py` (new function + any helpers)
- Modify: `src/gateway/web.py` (new route)
- Modify: `skills/review-and-improve/SKILL.md` (consume new data)
- New: `tests/test_retrospective_context.py` (pure-function tests for
  `parse_read_events` and whatever other helpers are extracted)
- Update: `.context/SYSTEM.md` (if retrospective.py dependencies change)
- Update: `.context/modules/runner/CHANGELOG.md` + `.context/modules/runner/CONTEXT.md`
- Update: `.context/modules/gateway/CHANGELOG.md`

## Tests

The pure-function helpers should have solid coverage. The async DB + audit
log walking is integration-tested only (no sandbox Postgres).

Commit message:

```
feat(rec-2): context consumption signal from audit logs

Per docs/EVALUATION_2026-04-18.md § 7 Recommendation 2.
Teaches review-and-improve what files are actually useful to skills by
walking audit logs for Read tool_use events and rolling up by
(skill, file_path).

- New: retrospective.context_consumption() rollup
- New: GET /api/retrospective/context route
- Modified: skills/review-and-improve/SKILL.md (Context files audit section)
- New: tests/test_retrospective_context.py
- Updated: SYSTEM.md + runner/gateway CONTEXT+CHANGELOG
```
