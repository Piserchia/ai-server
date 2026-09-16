# Pickem Trash-Talk Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a trash-talk board (free-name threads + comments, commissioner-only moderation, auto weekly threads) on the live pickem dashboard.

**Architecture:** New `app/board.py` service module owning validation, rate limiting (the proven `BEGIN IMMEDIATE` transactional pattern from `app/analysis/service.py`), and soft-delete storage over three new SQLite tables (additive migration → `user_version 2`); thin routes in `app/api.py`; weekly threads inserted by the sync inside the week transaction; one new lazy SPA route.

**Tech Stack:** Existing: FastAPI, stdlib sqlite3, pytest; React+TS+Vite (no new deps).

**Spec:** `docs/superpowers/specs/2026-09-16-pickem-trash-board-design.md` (ai-server repo). Read it first; it is the authority.

## Global Constraints

- Repo `~/Documents/repos/pickem` ($CANON), work on `main`, live site — never touch `volumes/pickem.db`, port 8793, or CBS; live pytest suite never runs.
- Limits (exact): title ≤120, author_name ≤40 single-line, thread body ≤2000 (MAY be empty), comment body ≤1000 (non-empty), cooldown 15s/IP, 10/hour/IP, 60/day/IP, 500/day global.
- All writes transactional (`BEGIN IMMEDIATE`, ledger + content in one txn, rollback on every early exit); connection arrives in autocommit (same invariant as `analysis/service.py` — document it).
- Content is data: stored verbatim post-clean, returned as JSON, rendered ONLY as React text nodes. No markdown, no linkification, no HTML path.
- Soft deletes only; comment tombstones keep ids; deleted threads 404.
- Weekly thread: kind='weekly', title `Week {week_id} Trash Talk`, author `League Bot`, body `Week {week_id}'s slate is up — talk your talk.` — idempotent per week_id.
- Existing DDL frozen; migration additive only. Ids bound-checked at API edges (house pattern). Admin = existing `require_admin`.
- Commit trailers on every commit:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01He8gi41ZYieS7HMwUXZi1H`

---

### Task 1: Migration v2 + board service module

**Files:**
- Modify: `$CANON/app/db.py` (versioned migration list)
- Create: `$CANON/app/board.py`
- Test: `$CANON/tests/test_board.py`

**Interfaces:**
- Consumes: `app.db.connect/migrate`; `tests/factory.py::build_season` (for week rows).
- Produces (Tasks 2–4 rely on these exact names):

```python
# app/board.py — constants
MAX_TITLE = 120; MAX_NAME = 40; MAX_THREAD_BODY = 2000; MAX_COMMENT_BODY = 1000
POST_COOLDOWN_S = 15; PER_IP_HOURLY = 10; PER_IP_DAILY = 60; GLOBAL_DAILY = 500

class BoardValidationError(ValueError):   # .detail: str (human-readable)
class BoardRateLimited(Exception):        # .detail: str, .retry_after_s: int

def clean_text(s: str | None, max_len: int, *, required: bool, single_line: bool = False) -> str
# strip control chars (keep \n unless single_line), trim; raise BoardValidationError on
# missing-required / too-long / empty-after-strip-when-required. Returns cleaned text ('' allowed when not required).

def list_threads(conn) -> list[dict]
# non-deleted, ≤200 rows, ordered last_activity DESC then id DESC. Row:
# {id, title, author_name, kind, week_id, created_at, comment_count (non-deleted), last_activity}

def get_thread(conn, thread_id: int) -> dict | None
# None if unknown or deleted. {id, title, author_name, kind, week_id, created_at,
#  comments: [{id, deleted: bool, author_name|None, body|None, created_at}]}  (tombstones: deleted=True, author/body None)

def create_thread(conn, ip_hash: str, *, title, author_name, body, now_utc: str | None = None) -> dict
def create_comment(conn, ip_hash: str, thread_id: int, *, author_name, body, now_utc: str | None = None) -> dict | None
# None = unknown/deleted thread (no txn side effects). Both: validate FIRST (no txn), then
# BEGIN IMMEDIATE → _rate_check → insert row → insert board_requests ledger row → commit;
# rollback+re-raise on BoardRateLimited/any error. Return the created row dict.

def soft_delete_thread(conn, thread_id: int) -> bool   # False if unknown; idempotent True if already deleted
def soft_delete_comment(conn, comment_id: int) -> bool

def ensure_weekly_thread(conn, week_id: int) -> bool
# INSERT kind='weekly' thread for week_id iff none exists (deleted ones count as existing —
# the commissioner deleting a weekly thread must stick). No ledger row, no rate check,
# NO transaction management of its own (caller owns the txn). Returns created?.
```

- DDL exactly as the spec §3; `migrate()` becomes a versioned list: `_MIGRATIONS = {1: [ ...existing SCHEMA... ], 2: [ ...board DDL... ]}` applied in order where `user_version <` key, ending `PRAGMA user_version = 2`. Existing DBs at version 1 get only the v2 statements; fresh DBs get both.

- [ ] **Step 1: failing tests** — `tests/test_board.py`: migration (fresh db → version 2 + 3 board tables; a db migrated under the OLD code path… simulate by creating v1 tables then re-running migrate → v2 additive, existing data intact); `clean_text` matrix (strips `\x00`/`\x07`, keeps `\n` multiline, rejects newline in single_line, trims, required-empty raises, over-length raises, empty allowed when not required); `create_thread` happy path + returned row; empty thread body legal; empty comment body raises; `create_comment` on unknown/deleted thread → None, no ledger row; cooldown (2nd post at +5s raises BoardRateLimited with retry_after_s>0, at +16s passes — drive with `now_utc`); hourly cap (11th in an hour raises); daily + global caps (monkeypatch constants small like the analysis tests); ledger row count == successful posts only; `list_threads` ordering (thread with newer comment outranks newer bare thread), comment_count excludes deleted, deleted thread absent, 201st thread absent (monkeypatch cap to 3 via module attribute `LIST_CAP`); `get_thread` tombstones; `soft_delete_*` idempotency; `ensure_weekly_thread` idempotent + respects-deleted; script-tag body stored verbatim (XSS is a rendering concern — assert round-trip equality).
- [ ] **Step 2:** `.venv/bin/pytest tests/test_board.py -q` → FAIL (no app.board).
- [ ] **Step 3:** implement `app/db.py` migration list + `app/board.py` (~200 lines; module docstring states the autocommit-connection invariant and points at `analysis/service.py` precedent; add `LIST_CAP = 200`).
- [ ] **Step 4:** `.venv/bin/pytest -q` → all green (319 + new).
- [ ] **Step 5:** commit `feat(board): migration v2 + board service (validation, transactional rate limits, soft deletes)`.

### Task 2: API routes

**Files:**
- Modify: `$CANON/app/api.py`
- Test: `$CANON/tests/test_board_api.py`

**Interfaces:**
- Consumes: Task 1's exact names; existing `get_conn`, `require_admin`, `_in_sqlite_int_range`, and the ip-hash helper pattern from `app/analysis/service.py` (sha256 of `request.client.host`).
- Produces routes: `GET /api/board/threads` → `{"threads": [...]}`; `GET /api/board/threads/{thread_id}` → thread dict | 404; `POST /api/board/threads` body `{title, author_name, body}` → 200 created row | 422 `{detail}` | 429 `{detail, retry_after_s}`; `POST /api/board/threads/{thread_id}/comments` body `{author_name, body}` → 200 | 404 | 422 | 429; `DELETE /api/board/threads/{thread_id}` and `DELETE /api/board/comments/{comment_id}` → `{"ok": true}` | 404, admin-gated. Pydantic request models with `max_length` ~4× the real caps (server-side clean_text is the authority; pydantic just stops megabyte bodies).

- [ ] **Step 1: failing tests** — `tests/test_board_api.py` with the existing TestClient fixture pattern: post→list→get→comment round trip; 422 on empty title with specific detail; 429 shape on cooldown (two immediate posts; assert retry_after_s); 404s (unknown thread, out-of-range huge id on all four id-routes); admin delete: 403 wrong token, 503 no token, 200 right token, thread 404s after, comment tombstones in get_thread; script-tag payload returned verbatim in JSON; **threaded cap test** (analysis-lane pattern: barrier + one connection per thread through the real route, monkeypatched small caps, assert exactly cap successes and ledger==cap).
- [ ] **Step 2:** run → FAIL. **Step 3:** implement (routes are thin: hash ip, call board.*, map BoardValidationError→422, BoardRateLimited→429 incl. Retry-After header, None→404). **Step 4:** full non-live suite green. **Step 5:** commit `feat(board): public board API with transactional rate limits + admin moderation`.

### Task 3: Weekly auto-thread in sync

**Files:**
- Modify: `$CANON/app/sync/run.py` (inside `_upsert_week`'s new-row branch, same transaction)
- Test: `$CANON/tests/test_sync.py` (extend)

**Interfaces:** Consumes `board.ensure_weekly_thread(conn, week_id)`. No shape changes to `run_sync`'s return.

- [ ] **Step 1: failing tests** — extend test_sync: after a sync creating week N, a kind='weekly' thread for N exists with the exact title/author/body strings from Global Constraints; second sync creates no duplicate; commissioner-deleted weekly thread stays deleted across re-syncs; a week-2-fails run (existing SyntheticClient case) leaves no week-2 thread (transaction rollback).
- [ ] **Step 2:** FAIL. **Step 3:** one call in the new-week branch. **Step 4:** suite green. **Step 5:** commit `feat(sync): auto-create weekly trash-talk thread with each new week`.

### Task 4: Board frontend

**Files:**
- Create: `$CANON/frontend/src/pages/Board.tsx`
- Modify: `$CANON/frontend/src/{App.tsx (lazy route + nav "Board"), api.ts (fetchers + types), theme.css (board styles)}`

**Interfaces:** Consumes Task 2's routes. Produces `api.ts`: `getBoardThreads()`, `getBoardThread(id)`, `postBoardThread(input)`, `postBoardComment(id, input)`, `deleteBoardThread(id, token)`, `deleteBoardComment(id, token)` — the deletes send `X-Admin-Token` and throw a typed `AdminAuthError` on 403 so the page can clear commissioner mode.

- [ ] **Step 1: implement** — one page file with internal components: `ThreadList` (rows: title, author, comment count, relative last-activity, LEAGUE badge for kind='weekly'; New-thread form with name prefill from localStorage `pickem_board_name`, live counters `x/120` etc.), `ThreadView` (body + comments as escaped text nodes with newlines via `white-space: pre-wrap`; muted tombstone rows "removed by the commissioner"; comment form; back link), commissioner mode (footer "commissioner" link → token prompt → localStorage `pickem_admin_token` → confirm-step delete buttons; any 403 clears the token + shows a notice). 422/429 errors render the server detail in the form; fetch errors get the Retry pattern from WeekPanel. Views are query-param routed (`/board`, `/board?t=<id>`) so deep links work with the existing SPA fallback.
- [ ] **Step 2: gates** — `npx tsc -b`, `npx oxlint --deny-warnings .`, `npm run build` clean; entry chunk gains no recharts (Board imports none).
- [ ] **Step 3: headless verify** on fixture DB copies (ports 8799+, never 8793): create thread → appears in list; comment → count/activity updates; 15s cooldown surfaces 429 copy; `<script>alert(1)</script>` body renders as literal text, zero console errors; commissioner mode: wrong token clears with notice, right token deletes (thread vanishes, comment tombstones); weekly thread shows LEAGUE badge; mobile 390px overflow 0; existing routes still clean.
- [ ] **Step 4:** commit `feat(frontend): trash-talk board (threads, comments, commissioner mode)`.

### Task 5: Release + docs

- [ ] **Step 1:** pickem docs: `.context/CONTEXT.md` (board in Architecture + Status; commissioner runbook: unlock location, token = PICKEM_ADMIN_TOKEN from prod `.env`), `.context/CHANGELOG.md` entry. Commit.
- [ ] **Step 2 (controller):** push canonical → prod `git pull --ff-only` → `npm ci && npm run build` in prod frontend → `launchctl kickstart -k gui/$(id -u)/com.assistant.project.pickem` (restart applies migration v2 on connect) → verify: `/healthz` 200; `sqlite3 volumes/pickem.db "PRAGMA user_version"` → 2; `GET /api/board/threads` 200 with week-2 weekly thread absent (created at next sync) or present if a sync ran; public URL: `/board` loads.
- [ ] **Step 3 (controller):** one live smoke as the commissioner: create a test thread via the public site, delete it via commissioner mode (owner token from prod .env, used server-side via curl -X DELETE with X-Admin-Token — never displayed), confirm tombstone/404 behavior. Update ai-server INDEX row → live. Final whole-diff review + ledger rulings to owner.

## Self-Review Notes

- Spec coverage: §2 identity/moderation → T2/T4; §3 DDL → T1; §4 API+limits → T1/T2; §5 weekly → T3; §6 frontend → T4; §7 errors → T1/T2/T4; §8 testing → per task; §9 release → T5. No gaps.
- Type consistency: BoardRateLimited.retry_after_s used in T1 def / T2 429 shape / T4 copy; ensure_weekly_thread(conn, week_id) signature identical T1/T3; fetcher names T4-internal.
- Deliberate scope holds (spec §10): no pagination (LIST_CAP 200 + monkeypatchable), no edits, no reactions.
