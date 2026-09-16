# Pickem Trash-Talk Board — Design Spec

- **Date**: 2026-09-16
- **Status**: APPROVED by owner (in-chat) — implementation plan next
- **Project**: `pickem` (live at pickem.chrispiserchia.com; repo `~/Documents/repos/pickem`)
- **Owner decisions**: free-text poster names (no verification — impersonation
  accepted as league culture); commissioner-only moderation; auto-created
  weekly threads; approach A (in-process board, same service/DB/SPA).

## 1. Mission

A trash-talk message board on the league dashboard: anyone with the link can
create note threads and comment on each other's threads. First user-generated
write surface on the site, so the design's center of gravity is abuse control
and effortless commissioner moderation — not features.

## 2. Semantics (owner-decided)

- **Identity**: poster name is free text (≤40 chars, trimmed, single-line).
  The browser remembers the last-used name (localStorage) purely as prefill.
  Nothing verifies names; posting as someone else is possible by design.
- **Moderation**: commissioner only. The Board page footer has a low-key
  "commissioner" unlock: paste the admin token once → stored in the browser's
  localStorage → delete controls appear on every thread and comment; DELETE
  calls carry `X-Admin-Token`. A 403 clears commissioner mode. No author
  self-deletes (no identity to authorize them).
- **Deletion display**: deleted comments leave a tombstone ("removed by the
  commissioner") preserving conversation shape; deleted threads disappear
  from the list (their page 404s).
- **Weekly anchor threads**: the sync creates one `kind='weekly'` thread per
  new week row — title "Week N Trash Talk", author "League Bot", body
  "Week N's slate is up — talk your talk." Idempotent per week_id.
- **Visibility**: world-readable like the rest of the site. Stated plainly:
  the board is on the public internet.

## 3. Data model (additive migration → `PRAGMA user_version = 2`)

```sql
board_threads(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL,            -- ≤120 chars
  author_name TEXT NOT NULL,                              -- ≤40 chars
  body TEXT NOT NULL DEFAULT '',                          -- ≤2000 chars
  kind TEXT NOT NULL DEFAULT 'user' CHECK(kind IN ('user','weekly')),
  week_id INTEGER REFERENCES weeks(id),                   -- weekly kind only
  created_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0)
board_comments(
  id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL REFERENCES board_threads(id),
  author_name TEXT NOT NULL, body TEXT NOT NULL,          -- ≤40 / ≤1000 chars
  created_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0)
board_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ip_hash TEXT NOT NULL, created_at TEXT NOT NULL)        -- write-rate ledger
```

Existing tables untouched (frozen-DDL discipline). Migration is additive and
idempotent, applied by the existing `migrate()` on service start/sync.

## 4. API (`app/api.py` + new `app/board.py` service module)

Public reads:
- `GET /api/board/threads` → non-deleted threads, ordered by last activity
  (max(created_at of thread, newest non-deleted comment)) desc; each row:
  id, title, author_name, kind, week_id, created_at, comment_count,
  last_activity. Hard cap 200 rows (no pagination v1; revisit if exceeded).
- `GET /api/board/threads/{id}` → thread + all comments in created order;
  deleted comments appear as `{deleted: true}` tombstones (no author/body);
  deleted/unknown thread → 404. Ids bound-checked (house pattern).

Rate-limited writes (per-IP via the verified XFF chain; sha256-hashed IPs in
`board_requests`; counting + insert inside ONE `BEGIN IMMEDIATE` transaction —
the proven analysis-lane pattern):
- `POST /api/board/threads` {title, author_name, body}
- `POST /api/board/threads/{id}/comments` {author_name, body}
- Limits: ≥15s between posts per IP; ≤10/hour per IP; ≤60/day per IP;
  ≤500/day global. Over-limit → 429 with friendly copy. Caps checked
  server-side: length limits above; title, author_name, and COMMENT body must
  be non-empty after strip (a THREAD body may be empty — title-only notes are
  legal); control characters stripped; author_name single-line. Payloads returned verbatim as data —
  rendering safety lives in the client's escaped-text rendering (React text
  nodes; no HTML path exists).

Admin (existing `require_admin`, constant-time compare):
- `DELETE /api/board/threads/{id}`, `DELETE /api/board/comments/{id}` —
  soft-delete (set `deleted=1`); idempotent; 404 unknown.

## 5. Weekly auto-thread (sync)

`app/sync/run.py`: after a NEW week row is inserted (same transaction), insert
the weekly thread if none exists for that week_id. No schedule, no LLM, no new
skills; the ai-server repo is untouched by this feature.

## 6. Frontend

New lazy route `/board` + nav link: 
- **Thread list**: title, author, comment count, relative last-activity;
  "New thread" form (name prefilled from localStorage, title, body,
  live length counters). Weekly threads get a small LEAGUE badge.
- **Thread view**: body + comments (escaped plain text, newlines preserved),
  comment form, tombstones rendered muted. Refetch after successful post
  (no polling); error/retry discipline as on the Analytics page.
- **Commissioner mode**: footer unlock → token prompt → localStorage;
  delete buttons with a confirm step; 403 clears mode with a notice.
- No markdown, no auto-linkified URLs (spam vector), no images. Emoji is just
  text and works. Mobile-first; overflow-contained like existing tables.

## 7. Error handling

Server: 422 validation (specific messages), 429 rate limit, 404 unknown/
deleted, 403/503 admin (existing semantics), transactional rollback on any
write failure. Client: form-level error display, retry buttons on fetch
failures, commissioner-mode 403 auto-clear.

## 8. Testing

- Backend TDD: validation matrix (lengths, empty, control chars, multiline
  name), rate limiter incl. the threaded barrier test (analysis-lane
  pattern: N parallel posts through the caps), tombstone semantics, list
  ordering by activity, weekly-thread idempotency (sync tests), admin
  delete paths, XSS probe (script/HTML stored verbatim, returned as JSON
  data — no server-side rendering path).
- Frontend: tsc/lint/build gates; headless verification with fixture DB
  copies (post/comment flows, limits surfacing as 429 copy, commissioner
  mode end-to-end incl. wrong-token clear, escaped rendering of a
  script-tag payload, mobile 390px, zero console errors). Production DB and
  port 8793 never touched by verification.

## 9. Release

Same lane as prior features: canonical commits (reviewed per chunk) → push →
prod runtime-clone pull → migration applies on restart → frontend rebuild →
service restart → live verification (public URL: board loads, a post →
delete cycle exercised once by the commissioner (owner's token), then the
test post removed). pickem CONTEXT/CHANGELOG updated; ai-server repo:
INDEX.md addition row only (this spec).

## 10. Out of scope (v1)

Accounts/PINs, editing posts, reactions/likes, pagination, live updates,
notifications, images/uploads, profanity filtering (it is a trash-talk
board), search.
