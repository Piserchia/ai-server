# Pick'em League Dashboard — Design Spec

- **Date**: 2026-09-09
- **Status**: APPROVED by owner (in-chat, 2026-09-09) — implementation plan next
- **Project slug**: `pickem`
- **Public URL**: `pickem.chrispiserchia.com` (openly accessible, no CF Access)
- **Owner decisions captured**: CBS Sports pool (owner is commissioner); picks
  against the spread; MNF-total tiebreaker judged by absolute difference;
  weekly ties cascade (tiebreaker → next week's total → next week's tiebreaker
  → …); season-end unresolvable ties split money as co-winners; 2026 season
  only; ingestion approach A (authenticated GraphQL); AI analysis cached +
  rate-limited; site name pulled from the CBS pool.

## 1. Mission

A public dashboard for the owner's 81-player NFL+college pick'em league
(CBS Sports pool, spread-based, 18 weeks): live leaderboards for every prize,
per-player pick analytics, head-to-head player comparison, and on-demand
AI-generated analysis of a player's pick history. Replaces ad-hoc HTML
scraping with a scheduled, validated GraphQL ingest.

### Prize structure (2026, total $4,050)

| Prize | Amount | Rule |
|---|---|---|
| 1st–5th season | 800 / 500 / 400 / 300 / 200 | Most correct picks on the season |
| Weekly | 50 × 18 | Most correct in the week; ties: cascade (below) |
| Brutus Buckeye College Champion | 250 | Most correct college (NCAAF) picks on the season |
| Race to the Bottom | 250 | Fewest correct on the season; **eligible only if every pick was made all season** (zero missed) |
| UnderDog Whisperer | 200 | Best win% on underdog picks, **minimum 75 underdog picks**; underdog = picked team was getting points at the pick's locked spread |
| Monday Night Lights | 250 | Most correct picks in NFL games kicking off on a Monday (America/New_York) on the season |

The former "highest single week" prize is removed.

### Tie rules (owner-confirmed)

- **Weekly (week W)**: most correct in W → smallest `abs(MNF-total guess −
  actual)` in W → most correct in W+1 → smallest tiebreaker error in W+1 → …
  A weekly winner can therefore be *provisional* until the cascade resolves;
  the UI shows "pending next week's tiebreak" in that state.
- **Season prizes**: total-correct ranking; unresolvable ties **split the
  covered prize money evenly** (e.g. two tied at 1st each get (800+500)/2;
  the next player takes 3rd). Side awards split their single prize.
- Tiebreaker closeness is **absolute difference** (over and under equal).

## 2. Platforms / Web Serving

- Primary platform: web. Served as `type: service` on **port 8793** behind
  Caddy + the Cloudflare tunnel at `pickem.chrispiserchia.com`.
- Openly accessible read-only. Admin/internal endpoints token-gated
  (`PICKEM_ADMIN_TOKEN`); never exposed in the UI.

## 3. Architecture

**Stack**: FastAPI + SQLite (server data dir), React + Vite + TypeScript SPA
(charts: Recharts) served by FastAPI `StaticFiles`. One process, one port.

**Topology**: dev-repo (2026-07-27 contract). Canonical
`~/Documents/repos/pickem` (private GitHub backup `Piserchia/pickem`);
`projects/pickem` is the pull-only runtime clone. Deploy via
`project-redeploy` with gates: pytest → `npm run build` (when `frontend/`
changed) → healthcheck `/healthz` 200.

**Data dir (prod)**: `<SERVER_ROOT>/volumes/pickem/` holds `pickem.db`
(SQLite) and `cbs_cookies.txt` (gitignored, owner-provisioned) — the
baseball-bingo precedent, outside the runtime clone so the pull-only guard
and deploys never touch data. Dev uses a local `./volumes/` via
`PICKEM_DATA_DIR`.

### Modules (canonical repo)

```
pickem/
  app/
    main.py            # FastAPI app: public API + StaticFiles + healthz
    db.py              # SQLite schema + migrations (schema_version pragma)
    models.py          # typed rows / pydantic response models
    cbs/
      client.py        # GraphQL client: cookie jar, browser-like headers,
                       # errors[] hard gate (4002 USER_LOGGED_OUT → abort)
      queries.py       # pinned query strings (harvested from live schema)
      ssr_fallback.py  # parse ApolloSSRDataTransport payload from
                       # authenticated HTML (fallback tier)
    sync/
      run.py           # CLI: python -m app.sync  (one full sync pass)
      mapper.py        # CBS → canonical mapping (weeks, games, picks)
      reconcile.py     # our computed weekly totals vs CBS periodScore;
                       # mismatch → flag in sync_runs, alert
    scoring/
      engine.py        # pure functions: all leaderboards + prize states
      tiebreak.py      # weekly cascade resolver
      stats.py         # per-player tendencies, comparisons, league analytics
    analysis/
      service.py       # AI-analysis request lifecycle, cache, rate limits
  frontend/            # Vite + React + TS SPA (dist/ served by FastAPI)
  reference/           # introspected CBS schema (schema_full.json etc.)
  tests/               # pytest — engine, mapper, tiebreak, API
  manifest.yml, CLAUDE.md, .context/{CONTEXT.md,CHANGELOG.md}
```

### Data model (SQLite)

- `players` (id, cbs_entry_id, name, active)
- `weeks` (id=ordinal 1..18, cbs_period_id, nfl_week, ncaaf_week, status)
  — **canonical week = CBS PoolPeriod**; NFL and NCAAF week numbers diverge
  (live-verified: NFL W1 = NCAAF W2) and are stored per sport, never used as
  the join key.
- `games` (id, week_id, cbs_event_id, sport NFL|NCAAF, kickoff_utc,
  home/away team, pool_spread, is_monday_night, tiebreaker_order,
  home_score, away_score, status)
- `picks` (player_id, game_id, picked_team, pick_spread /*EntryPick.spread —
  authoritative line at pick time*/, result CORRECT|INCORRECT|NONE,
  display_status) — **only post-lock data is ever stored**; nothing on the
  public site can leak a pick before CBS itself shows it.
- `tiebreaker_answers` (player_id, week_id, value)
- `analyses` (player_id, through_week, markdown, model, created_at) — AI cache
- `sync_runs` (started_at, ok, weeks_touched, games/picks upserted,
  reconcile_ok, error) — audit trail surfaced on an admin status page
- `analysis_requests` (for rate limiting: ip_hash, created_at)

### Ingestion (approach A — authenticated GraphQL)

- Endpoint `https://picks.cbssports.com/graphql` (service "picks2"), cookie
  auth from `cbs_cookies.txt` (full cbssports.com cookie jar; exact
  load-bearing cookie names unknown, so the whole jar is stored). Introspected
  schema (491 types) vendored in `reference/`.
- Entry points: `commonPool(id)` / `commonPoolBySlug` with
  `FootballPickemManagerPool` fragment → `poolPeriods`, `allEntries`,
  `standings.weekly.rankedEntries` (picks grid:
  `picks[{cbsSlotId, displayStatus, pickInfo{cbsItemId, pickStatus}}]`,
  `tiebreakerAnswers`), pool events (`sportType`, `homeTeamSpread`,
  `tiebreakerOrder`), `EntryPick.spread` per entry, pool settings (site
  title from pool name; `spreadType`, deadlines).
- **Hard gates**: any `errors[]` entry (esp. code 4002 `USER_LOGGED_OUT`)
  aborts the run before any write — CBS returns HTTP 200 + partial data on
  auth expiry. Every run starts with a cheap authenticated probe; on auth
  failure the run exits non-zero with `AUTH_EXPIRED` so the skill layer
  alerts the owner (Telegram) to re-export cookies.
- **Cadence**: 4 runs/week at 09:00 UTC (05:00 ET), cron `0 9 * * 0,1,2,5` —
  Sun (post-Saturday college), Mon (post-Sunday NFL), Tue (post-MNF: final
  grading + tiebreakers + weekly winner), Fri (post-TNF/Thu college). One
  run ≈ 4–6 requests; browser-like headers; no parallel hammering
  (ToS-conscious: less total traffic than a single page view).
- **Fallback tier**: `ssr_fallback.py` parses the ApolloSSRDataTransport
  JSON embedded in authenticated standings HTML — survives API-shape drift;
  doubles as a query-drift detector. Last resort: `POST /api/internal/import`
  (admin-token) accepts a manually pasted grid.
- **Reconciliation**: after each sync, our computed weekly totals are checked
  against CBS `periodScore` per entry; any mismatch marks the run
  `reconcile_ok = false` and is alerted — this catches mulligan/missed-pick
  penalty semantics we haven't seen yet, silently-changed grading, and
  mapper bugs.
- **Scheduling**: ai-server `schedules` row `pickem-sync-daily`
  (`0 9 * * *`, kind `pickem-sync`) seeded via `scripts/seed-schedules.sh` —
  a thin skill (isolation: none) that runs the runtime clone's
  `.venv/bin/python -m app.sync` against `volumes/pickem/`, reports the
  sync_runs outcome, and surfaces AUTH_EXPIRED loudly. Rides the existing
  audit-log, failure-escalation, and schedule-adherence machinery.

### Backfill

2026 season only. First sync with real cookies backfills all completed
periods (week 1 NFL / weeks 1–2 NCAAF) through the same pipeline as the
weekly run — backfill is not special-cased. Open uncertainties (allEntries
pagination at 81 players, manager pre-lock visibility) resolve at first
authenticated run; cadence only needs post-lock reads, so pre-lock
visibility is a nice-to-have, not a dependency.

### Web app (public, read-only)

- `GET /healthz`; `GET /api/meta` (pool name, week, last-sync)
- `GET /api/leaderboards` — all six prize races incl. weekly-winner history,
  provisional-tiebreak states, running money won per player
- `GET /api/players`, `GET /api/players/{id}` — profile, pick history grid,
  tendencies (fav/dog rate + success, home/away lean, NFL vs NCAAF splits,
  most/least-picked teams, streaks, rank trajectory, consensus vs contrarian
  record, MNF record, tiebreaker accuracy)
- `GET /api/compare?players=a,b[,c…]` — side-by-side stats
- `GET /api/analytics` — league-wide: consensus per game, most/least trusted
  teams, upset success, all-favorites benchmark, weekly difficulty
- `POST /api/players/{id}/analysis` + `GET …/analysis` — AI analysis (below)
- Admin (token): `POST /api/internal/import`, `POST /api/internal/analyses`,
  `GET /api/internal/sync-status`

SPA pages: **Leaderboards** (default), **Player** (with "Generate AI
analysis"), **Compare**, **League analytics**. Mobile-friendly; league
name from CBS pool settings.

### AI analysis pipeline

1. `POST /api/players/{id}/analysis` → rate-limit check (global 24/day,
   3/day/IP, one in-flight per player) → if cache fresh for
   (player, current week) return cached.
2. Service enqueues on the ai-server runner (the subscription-auth lane with
   quota auto-pause): `POST http://127.0.0.1:8080/api/jobs` with
   `WEB_AUTH_TOKEN` from its env; kind = **`pickem-analysis`** (new skill,
   isolation: none, cheap model per skill frontmatter).
3. The skill session reads `GET /api/players/{id}` +
   `GET /api/leaderboards` from localhost:8793, writes ~300-word markdown
   (tendencies, strengths, funny/sharp observations, prize outlook) back via
   `POST /api/internal/analyses` (admin token from skill context).
4. UI polls `GET /api/players/{id}/analysis` until the cache row appears
   (states: none / generating / ready / error+retry-after).

### Error handling summary

- Sync: auth-expiry hard-abort + owner alert; partial-data impossible by
  gate; reconcile mismatch alerts but keeps serving last-good data.
- Web: DB-read-only endpoints degrade to last-good snapshot; `/healthz`
  checks DB readability + last-sync age (warn >48h in `/api/meta`).
- AI: runner quota pause → job queues; UI shows "generating" then
  "try later" after timeout; failures cached briefly to prevent hammering.

## 4. Testing

- pytest: scoring engine golden cases (all six prizes incl. eligibility
  edges: missed-pick disqualification, <75 dogs, split math), weekly cascade
  (multi-week chains, provisional states, season-end split), mapper fixtures
  from recorded GraphQL responses (week divergence NFL/NCAAF, LOCKED/
  MISSING/MULLIGAN statuses, pick-time vs pool spread), reconcile mismatch
  detection, API smoke tests (httpx), rate limiter.
- Frontend: `npm run build` as deploy gate; component logic kept thin.
- Server side: `python scripts/lint_docs.py` (registry sync) + existing
  pytest suite must stay green when the skill + schedule rows land.

## 5. Ops / registration checklist (build-time)

1. Port **8793** appended to `projects/_ports.yml`; row added to
   `.context/PROJECTS_REGISTRY.md`; INDEX.md addition row.
2. `manifest.yml` with delivery block (dev-repo, pull-only, gated-auto,
   gates above, `env_files: [".env"]`).
3. `register-project.sh pickem` on prod (Caddy snippet, launchd plist,
   DB row, DNS route, healthcheck probe).
4. New skill `skills/pickem-sync/` + `skills/pickem-analysis/` →
   `.context/SKILLS_REGISTRY.md`; schedule row in `seed-schedules.sh`
   (payload `{"project_slug":"pickem"}`).
5. Owner provisioning (the only human steps): paste pool URL/ID into project
   `.env`; export cbssports.com cookie jar to
   `volumes/pickem/cbs_cookies.txt` (one-minute recipe provided at build).

## 6. Risks (accepted at approval)

- **Unofficial API**: CBS can change schema/auth mid-season without notice.
  Mitigations: pinned queries + SSR-payload fallback + manual import; vendored
  schema for diffing. Accepted.
- **ToS exposure**: automated access with the owner's account. Mitigated by
  ~1 gentle run/day (less than a page view); accepted by owner with approach A.
- **Cookie expiry** (lifetime unmeasured): auth probe + Telegram alert;
  post-lock data is recoverable after re-login, so worst case is a stale
  dashboard, never lost picks.
- **Grading semantics** (mulligans/penalties unverified): reconciliation
  against CBS `periodScore` catches divergence before it misleads anyone.
- **Season-boundary**: pool settings (weights, postseason) re-read every
  sync; engine is game-count agnostic.

## 7. Out of scope (v1)

Past seasons; live in-game scoreboards; push notifications to players;
pick submission (read-only mirror of CBS); postseason weeks (revisit at
week 18); auth for visitors (link-open by design).
