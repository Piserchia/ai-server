# Pick'em League Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy `pickem.chrispiserchia.com` — a public dashboard for the 81-player "Arlington Degenerates" CBS pick'em pool: CBS GraphQL ingest, all six prize leaderboards, player analytics/comparison, and cached AI analysis.

**Architecture:** FastAPI + SQLite backend with a deterministic CBS GraphQL sync (cookie-auth, hard-abort on auth errors, reconciliation against CBS's own scores), a pure-function scoring/prize engine, and a Vite+React SPA served by the same process. AI analysis runs as jobs on the ai-server runner (subscription lane). Dev-repo topology: canonical `~/Documents/repos/pickem`, pull-only runtime clone `projects/pickem`.

**Tech Stack:** Python 3.11+ (FastAPI, uvicorn, httpx, pytest; stdlib sqlite3 — no ORM), Vite + React + TypeScript + react-router + Recharts, ai-server skills/schedules for ops.

**Spec:** `docs/superpowers/specs/2026-09-09-pickem-league-design.md` (ai-server repo). Read it first; this plan argues from it.

## Global Constraints

- Canonical repo `~/Documents/repos/pickem` ($CANON below); NEVER edit `projects/pickem` (pull-only runtime clone). ai-server repo = `~/Documents/repos/ai-server`.
- Port **8793**; public URL `pickem.chrispiserchia.com`; no CF Access.
- Pool: id `kbxw63b2ge3dknjzga2tc===` (= `Pool:16559051`), name "Arlington Degenerates" (display name always read from DB meta, never hardcoded in UI).
- Cookies live ONLY in `$CANON/.secrets/cbs_cookie_header.txt` (dev) and `$SERVER_ROOT/volumes/pickem/cbs_cookie_header.txt` (prod). Never in git, never in chat, never in test fixtures.
- CBS traffic: ≤1 request burst per run, 4 scheduled runs/week (`0 9 * * 0,1,2,5` UTC); browser-like headers; any GraphQL `errors[]` entry aborts the run BEFORE any DB write.
- Only post-lock data is stored (CBS enforces via `displayStatus`; we store whatever CBS shows us and nothing marked LOCKED).
- `ANTHROPIC_API_KEY` must never appear anywhere. AI analysis goes through the ai-server gateway job lane only.
- Prizes (exact): season [800,500,400,300,200]; weekly 50; Brutus 250; Bottom 250 (zero missed picks required); UnderDog 200 (≥75 underdog picks); Monday Night Lights 250. Tiebreaker = absolute difference; season-end unresolvable ties split covered money evenly.
- ai-server repo changes (Tasks 16, 18): INV-13 — code-review agent LGTM before push; `git fetch origin && git merge origin/main` before starting and before pushing; `python scripts/lint_docs.py` + `pipenv run pytest -q` green.
- Python style: type hints on public functions; tests colocated in `$CANON/tests/`.

---

### Task 1: Canonical repo scaffold + config

**Files:**
- Create: `$CANON/{requirements.txt,.env.example,README.md,app/__init__.py,app/config.py,tests/__init__.py,tests/test_config.py}`
- Already present (keep): `$CANON/.gitignore`, `$CANON/scripts/export_cbs_cookies.py`, `$CANON/reference/*.json`, `$CANON/.secrets/` (never add to git)

**Interfaces:**
- Produces: `app.config.Settings` (frozen dataclass) and `get_settings() -> Settings` reading env with defaults:
  `data_dir` (PICKEM_DATA_DIR, default `$CANON/volumes`), `pool_id` (PICKEM_POOL_ID, default `kbxw63b2ge3dknjzga2tc===`), `cookie_file` (PICKEM_COOKIE_FILE, default `$CANON/.secrets/cbs_cookie_header.txt`), `admin_token` (PICKEM_ADMIN_TOKEN, default `""` = internal endpoints disabled), `gateway_url` (PICKEM_GATEWAY_URL, default `http://127.0.0.1:8080`), `gateway_token` (PICKEM_GATEWAY_TOKEN, default `""`), `fake_analysis` (PICKEM_FAKE_ANALYSIS, default `False`), `season_final_week` (PICKEM_SEASON_FINAL_WEEK, default `18`), `db_path` property = `data_dir/pickem.db`.
- Produces: prize constants in `app/config.py`: `SEASON_PRIZES = [800, 500, 400, 300, 200]`, `WEEKLY_PRIZE = 50`, `PRIZE_BRUTUS = 250`, `PRIZE_BOTTOM = 250`, `PRIZE_UNDERDOG = 200`, `PRIZE_MNL = 250`, `UNDERDOG_MIN_PICKS = 75`.

- [ ] **Step 1: Write the failing test** `tests/test_config.py`:

```python
import os
from app.config import get_settings, SEASON_PRIZES, UNDERDOG_MIN_PICKS

def test_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("PICKEM_DATA_DIR", str(tmp_path))
    s = get_settings()
    assert s.db_path == str(tmp_path / "pickem.db")
    assert s.pool_id == "kbxw63b2ge3dknjzga2tc==="
    assert s.season_final_week == 18
    assert s.admin_token == ""
    assert SEASON_PRIZES == [800, 500, 400, 300, 200]
    assert UNDERDOG_MIN_PICKS == 75

def test_env_overrides(monkeypatch):
    monkeypatch.setenv("PICKEM_FAKE_ANALYSIS", "1")
    monkeypatch.setenv("PICKEM_SEASON_FINAL_WEEK", "17")
    s = get_settings()
    assert s.fake_analysis is True and s.season_final_week == 17
```

- [ ] **Step 2:** `cd $CANON && python3 -m venv .venv && .venv/bin/pip install fastapi 'uvicorn[standard]' httpx pytest && .venv/bin/pytest tests/test_config.py -q` — expect FAIL (no app.config). Write `requirements.txt`: `fastapi`, `uvicorn[standard]`, `httpx`, `pytest` (one per line).
- [ ] **Step 3:** Implement `app/config.py`:

```python
import os
from dataclasses import dataclass
from pathlib import Path

SEASON_PRIZES = [800, 500, 400, 300, 200]
WEEKLY_PRIZE = 50
PRIZE_BRUTUS = 250
PRIZE_BOTTOM = 250
PRIZE_UNDERDOG = 200
PRIZE_MNL = 250
UNDERDOG_MIN_PICKS = 75

_REPO = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    data_dir: str
    pool_id: str
    cookie_file: str
    admin_token: str
    gateway_url: str
    gateway_token: str
    fake_analysis: bool
    season_final_week: int

    @property
    def db_path(self) -> str:
        return str(Path(self.data_dir) / "pickem.db")

def get_settings() -> Settings:
    return Settings(
        data_dir=os.environ.get("PICKEM_DATA_DIR", str(_REPO / "volumes")),
        pool_id=os.environ.get("PICKEM_POOL_ID", "kbxw63b2ge3dknjzga2tc==="),
        cookie_file=os.environ.get("PICKEM_COOKIE_FILE", str(_REPO / ".secrets" / "cbs_cookie_header.txt")),
        admin_token=os.environ.get("PICKEM_ADMIN_TOKEN", ""),
        gateway_url=os.environ.get("PICKEM_GATEWAY_URL", "http://127.0.0.1:8080"),
        gateway_token=os.environ.get("PICKEM_GATEWAY_TOKEN", ""),
        fake_analysis=os.environ.get("PICKEM_FAKE_ANALYSIS", "") in ("1", "true", "yes"),
        season_final_week=int(os.environ.get("PICKEM_SEASON_FINAL_WEEK", "18")),
    )
```

`.env.example` lists every PICKEM_* var above with the default as value and a one-line comment. `README.md`: 10 lines — what it is, dev quickstart (`.venv`, pytest, `python -m app.sync`, `uvicorn app.main:app`), pointer to spec in ai-server repo.
- [ ] **Step 4:** `.venv/bin/pytest tests/ -q` — expect 2 passed.
- [ ] **Step 5:** Init + first commit + GitHub backup:

```bash
cd $CANON && git init -b main && git add -A && git commit -m "scaffold: config, prize constants, cookie export script, CBS schema reference"
gh repo create Piserchia/pickem --private --source=. --remote=origin --push
```

If `gh repo create` fails, report it and continue (local-only is acceptable until Task 17).

---

### Task 2: SQLite schema + season fixture factory

**Files:**
- Create: `$CANON/app/db.py`, `$CANON/tests/factory.py`, `$CANON/tests/conftest.py`, `$CANON/tests/test_db.py`

**Interfaces:**
- Produces: `app.db.connect(db_path: str) -> sqlite3.Connection` (row_factory returns dicts, WAL, foreign_keys ON, creates parent dir), `app.db.migrate(conn) -> None` (idempotent, `PRAGMA user_version`).
- Produces tables (exact columns — later tasks depend on these names):
  - `players(id INTEGER PRIMARY KEY, cbs_entry_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)`
  - `weeks(id INTEGER PRIMARY KEY, cbs_period_id TEXT UNIQUE NOT NULL, nfl_week INTEGER, ncaaf_week INTEGER, status TEXT NOT NULL DEFAULT 'open')`  — `id` is the canonical ordinal 1..N; status `open|final`
  - `games(id INTEGER PRIMARY KEY, week_id INTEGER NOT NULL REFERENCES weeks(id), cbs_event_id TEXT UNIQUE NOT NULL, sport TEXT NOT NULL CHECK(sport IN ('NFL','NCAAF')), kickoff_utc TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL, pool_spread REAL, is_monday_night INTEGER NOT NULL DEFAULT 0, tiebreaker_order INTEGER, home_score INTEGER, away_score INTEGER, status TEXT NOT NULL DEFAULT 'scheduled')` — status `scheduled|final`; `pool_spread` is the HOME team's line (negative = home favored)
  - `picks(player_id INTEGER NOT NULL REFERENCES players(id), game_id INTEGER NOT NULL REFERENCES games(id), picked_team TEXT CHECK(picked_team IN ('HOME','AWAY')), pick_spread REAL, result TEXT NOT NULL DEFAULT 'PENDING' CHECK(result IN ('CORRECT','INCORRECT','PENDING','MISSING')), display_status TEXT, PRIMARY KEY(player_id, game_id))` — `pick_spread` is from the PICKED team's perspective (positive = picked team getting points → underdog pick)
  - `tiebreaker_answers(player_id INTEGER NOT NULL, week_id INTEGER NOT NULL, value REAL NOT NULL, PRIMARY KEY(player_id, week_id))`
  - `analyses(player_id INTEGER NOT NULL, through_week INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'generating' CHECK(status IN ('generating','ready','error')), markdown TEXT, model TEXT, created_at TEXT NOT NULL, PRIMARY KEY(player_id, through_week))`
  - `analysis_requests(id INTEGER PRIMARY KEY AUTOINCREMENT, ip_hash TEXT NOT NULL, player_id INTEGER NOT NULL, created_at TEXT NOT NULL)`
  - `sync_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT, ok INTEGER, weeks_touched TEXT, games_upserted INTEGER DEFAULT 0, picks_upserted INTEGER DEFAULT 0, reconcile_ok INTEGER, error TEXT)`
  - `meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)` — keys used later: `pool_name`, `season_year`, `last_sync_at`
- Produces: `tests/factory.py :: build_season(conn, weeks: list[dict]) -> None`. Each week dict: `{"nfl_week": 1, "games": [{"sport": "NFL", "home": "DAL", "away": "NYG", "spread": -3.5, "kickoff": "2026-09-13T17:00:00+00:00", "mnf": False, "tb": False, "final": (27, 20)}], "picks": {"alice": [("HOME", "CORRECT"), ...]}, "tb_answers": {"alice": 45}}` — creates players on first sight (name = key, cbs_entry_id = `e-<name>`), games (`cbs_event_id` = `ev-<week>-<idx>`), picks in game order (`pick_spread` derived: HOME → spread, AWAY → −spread; a `("MISS",)` tuple → picked_team NULL, result MISSING), tiebreaker answers; sets week status final iff every game final.
- Produces: `tests/conftest.py` fixture `db` → in-memory-style connection on `tmp_path`, migrated.

- [ ] **Step 1:** Write `tests/test_db.py`: migrate creates all 9 tables (query `sqlite_master`), migrate twice is a no-op, `build_season` with one 2-game week yields 2 players / 2 games / 4 picks and week status final; a `("MISS",)` pick stores `result='MISSING'` and NULL `picked_team`; AWAY pick on home-spread −3.5 stores `pick_spread=3.5`.
- [ ] **Step 2:** Run: `.venv/bin/pytest tests/test_db.py -q` — FAIL (no app.db).
- [ ] **Step 3:** Implement `app/db.py` (single `SCHEMA` list of `CREATE TABLE IF NOT EXISTS` statements executed in order; `user_version` set to 1) and the factory + conftest.
- [ ] **Step 4:** `.venv/bin/pytest -q` — all pass.
- [ ] **Step 5:** `git add -A && git commit -m "feat: sqlite schema + season fixture factory"`

---

### Task 3: CBS GraphQL client with auth hard-gate

**Files:**
- Create: `$CANON/app/cbs/__init__.py`, `$CANON/app/cbs/client.py`, `$CANON/tests/test_client.py`

**Interfaces:**
- Produces: `app.cbs.client.CBSAuthError(Exception)`, `CBSQueryError(Exception)`, and

```python
class CBSClient:
    ENDPOINT = "https://picks.cbssports.com/graphql"
    def __init__(self, cookie_header: str, transport: httpx.BaseTransport | None = None): ...
    @classmethod
    def from_file(cls, path: str) -> "CBSClient": ...   # reads header line, strips
    def query(self, gql: str, variables: dict | None = None) -> dict: ...  # returns payload["data"]
```

- `query()` behavior (the hard gate): POST JSON `{"query": gql, "variables": variables or {}}` with headers Cookie, browser-like User-Agent, `Origin`/`Referer` = `https://picks.cbssports.com`. If response JSON has a non-empty `errors` list: raise `CBSAuthError` if any error's `extensions`/top-level `code` equals `"4002"` or `statusCode == "USER_LOGGED_OUT"`, else `CBSQueryError(str(errors))`. Never return partial data. Non-200 or network error → `CBSQueryError`. The optional `transport` arg is for tests (`httpx.MockTransport`).

- [ ] **Step 1:** Write `tests/test_client.py` using `httpx.MockTransport`: (a) ok payload returns `data`; (b) `{"data": {...}, "errors": [{"code": "4002", "statusCode": "USER_LOGGED_OUT"}]}` raises CBSAuthError even though data is present; (c) other errors raise CBSQueryError; (d) `from_file` loads and strips the header line (write a fake cookie file in tmp_path); (e) request carries Cookie header and User-Agent containing "Mozilla" (assert inside the mock handler).
- [ ] **Step 2:** `.venv/bin/pytest tests/test_client.py -q` — FAIL.
- [ ] **Step 3:** Implement (≈50 lines; `httpx.Client(transport=...)` held on the instance; error-code scan checks both `err.get("code")` and `err.get("extensions", {}).get("code")` and `err.get("statusCode")`).
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass.
- [ ] **Step 5:** `git add -A && git commit -m "feat: CBS GraphQL client with USER_LOGGED_OUT hard gate"`

---

### Task 4: Pinned queries + live probe + fixture capture

**Files:**
- Create: `$CANON/app/cbs/queries.py`, `$CANON/scripts/dev_probe.py`, `$CANON/tests/test_queries_live.py`, `$CANON/tests/fixtures/` (captured JSON), `$CANON/pytest.ini`

**Interfaces:**
- Produces in `queries.py` (module constants, exact names): `POOL_META`, `POOL_PERIODS`, `WEEK_EVENTS`, `WEEK_STANDINGS`, `ENTRY_PICKS`. All use `$poolId: ID!` (+ `$periodId: ID!` where noted).
- Produces fixture files consumed by Task 5: `tests/fixtures/{pool_meta,pool_periods,week_events,week_standings,entry_picks}.json` — each the raw `data` dict returned by `CBSClient.query`, **with entry names pseudonymized** (see Step 3).
- `pytest.ini` registers marker `live` and sets `addopts = -m "not live"` so live tests only run when explicitly selected.

**Starting query shapes** (from the 2026-09-09 live introspection — the deliverable of this task is these queries *verified against the real pool*, amended as the schema demands; consult `reference/schema_full.json` for any field that errors):

```graphql
# POOL_META
query PoolMeta($poolId: ID!) { commonPool(id: $poolId) {
  id slug name season { year } gameInstanceUid
  ... on FootballPickemManagerPool { isUsingSpread poolSettings { __typename } } } }

# POOL_PERIODS
query PoolPeriods($poolId: ID!) { commonPool(id: $poolId) {
  id ... on FootballPickemManagerPool { poolPeriods {
    id order description startsAt endsAt
    weeks { weekNumber sportType } } } } }

# WEEK_EVENTS
query WeekEvents($poolId: ID!, $periodId: ID!) { commonPool(id: $poolId) {
  id ... on FootballPickemManagerPool { poolEvents(periodId: $periodId) {
    id cbsEventId sportType startsAt homeTeamSpread tiebreakerOrder
    homeTeam { abbrev name } awayTeam { abbrev name }
    homeTeamScore awayTeamScore gameStatus } } } }

# WEEK_STANDINGS
query WeekStandings($poolId: ID!, $periodId: ID!) { commonPool(id: $poolId) {
  id ... on FootballPickemManagerPool { standings { weekly(periodId: $periodId) {
    rankedEntries { rank score periodScore
      entry { id name }
      picks { cbsSlotId displayStatus pickInfo { cbsItemId pickStatus } }
      tiebreakerAnswers { tiebreakerQuestionId displayStatus tiebreakerAnswerInfo { value } } } } } } } }

# ENTRY_PICKS
query EntryPicks($poolId: ID!, $periodId: ID!) { commonPool(id: $poolId) {
  id ... on FootballPickemManagerPool { allEntries {
    id name picks(poolPeriodId: $periodId) {
      slotId cbsSlotId itemId cbsItemId
      spread { spread spreadForItemId spreadForCbsItemId spreadBook } } } } } }
```

- [ ] **Step 1:** Write `scripts/dev_probe.py`: loads Settings, builds `CBSClient.from_file(settings.cookie_file)`, runs each query in `queries.py` in order (periods first to discover a `periodId` — use the earliest period), pretty-prints a 5-line summary per query (counts, first entry name, first event), and with `--save` writes each `data` payload to `tests/fixtures/<name>.json` after pseudonymizing: replace every entry `name` with `Player01..PlayerNN` (stable mapping by sorted original name; write the mapping to `.secrets/name_map.json`, NOT to fixtures) and strip any email-like strings. Exit non-zero on CBSAuthError with message "AUTH_EXPIRED — re-run scripts/export_cbs_cookies.py".
- [ ] **Step 2:** Write `tests/test_queries_live.py` (all `@pytest.mark.live`): one test per query constant — runs it against the real endpoint with the real cookie file and asserts the response contains the expected top-level shape (e.g. WEEK_STANDINGS yields ≥1 rankedEntry with a picks list). Plus `test_pool_is_ours`: `POOL_META` name == "Arlington Degenerates".
- [ ] **Step 3:** Iterate: `.venv/bin/pytest -m live -q` and `.venv/bin/python scripts/dev_probe.py`. **Expect field-name churn here** — fix `queries.py` against `reference/schema_full.json` (grep the type, e.g. `python3 -c "import json;s=json.load(open('reference/schema_full.json'))..."` or plain `grep -o` for field names) until all five run clean. This step is done when the live suite passes; if a whole query proves structurally wrong (e.g. `poolEvents` doesn't take `periodId`), rewrite it per the schema — the constant names and fixture filenames are the frozen contract, not the internal shape. Record any shape changes in the commit message.
- [ ] **Step 4:** `.venv/bin/python scripts/dev_probe.py --save` — fixtures captured. Manually eyeball `tests/fixtures/week_standings.json`: ranked entries ≈ 81, names pseudonymized, no cookies/emails anywhere: `grep -ri "cookie\|@gmail\|@yahoo" tests/fixtures/ || echo CLEAN`.
- [ ] **Step 5:** `git add -A && git commit -m "feat: pinned CBS queries verified live + pseudonymized fixtures"`

---

### Task 5: Mapper (raw GraphQL → normalized rows)

**Files:**
- Create: `$CANON/app/sync/__init__.py`, `$CANON/app/sync/mapper.py`, `$CANON/tests/test_mapper.py`

**Interfaces:**
- Consumes: fixture JSONs from Task 4; DB schema from Task 2.
- Produces (all pure functions over parsed JSON `data` dicts):

```python
def map_periods(data: dict) -> list[dict]
# [{"ordinal": 1, "cbs_period_id": "...", "nfl_week": 1, "ncaaf_week": 2}], ordered by startsAt;
# nfl_week/ncaaf_week from the period's weeks[] by sportType (None if absent)

def map_events(data: dict) -> list[dict]
# [{"cbs_event_id", "sport" ('NFL'|'NCAAF'), "kickoff_utc" (ISO8601 UTC), "home_team", "away_team",
#   "pool_spread" (float|None, HOME perspective), "is_monday_night" (bool), "tiebreaker_order" (int|None),
#   "home_score", "away_score", "status" ('final' iff gameStatus says complete else 'scheduled')}]

def map_standings(data: dict, slot_to_event: dict[str, str], item_to_side: dict[str, str]) -> dict
# {"players": [{"cbs_entry_id", "name"}],
#  "picks": [{"cbs_entry_id", "cbs_event_id", "picked_team" ('HOME'|'AWAY'|None), "result", "display_status"}],
#  "tb_answers": [{"cbs_entry_id", "value"}], "period_scores": {"cbs_entry_id": int}}
# result mapping: pickStatus CORRECT→CORRECT, INCORRECT→INCORRECT, NONE→PENDING;
# displayStatus MISSING (or missing pickInfo) → picked_team None, result MISSING; LOCKED entries are SKIPPED entirely.

def map_entry_spreads(data: dict) -> dict[tuple[str, str], tuple[float, str]]
# {(cbs_entry_id, cbs_slot_id): (spread_value, spread_for_cbs_item_id)}

def pick_spread_for(picked_item: str, home_item: str, entry_spread: tuple[float, str] | None,
                    pool_spread_home: float | None) -> float | None
# perspective normalization: returns the picked team's line (positive = getting points).
# Prefers entry_spread (flip sign if spread_for item != picked item); falls back to pool_spread_home
# (flip sign if picked AWAY); None if neither available.

def is_monday_night(kickoff_utc_iso: str, sport: str) -> bool
# NFL and kickoff converted to America/New_York falls on Monday (zoneinfo; weekday()==0)
```

- The `slot_to_event` / `item_to_side` lookup dicts are built by the sync (Task 6) from `WEEK_EVENTS` results; mapper stays pure. **Note for implementer:** exact slot→event and item→team-side linkage lives in the fixture data — inspect `tests/fixtures/week_events.json` + `week_standings.json` + `entry_picks.json` side by side FIRST; if the real linkage differs from `cbsSlotId`/`cbsItemId` assumptions, adjust the two lookup-dict parameters' semantics and document in the docstring (the fixtures are ground truth, captured from the real pool).

- [ ] **Step 1:** Write `tests/test_mapper.py` — two layers: (a) real-fixture tests: `map_periods`/`map_events`/`map_standings`/`map_entry_spreads` over the Task-4 fixtures assert non-empty output, every pick's result ∈ the enum, ≈81 players, and NFL/NCAAF both present in events; (b) handcrafted micro-payload tests for the edges: NFL-Monday kickoff 00:15 UTC Tuesday (= Monday 8:15pm ET) → `is_monday_night` True; Saturday NCAAF → False; `pick_spread_for("i2", "i1", (3.5, "i2"), -3.5) == 3.5` (entry spread already for picked item), `pick_spread_for("i2", "i1", (−3.5, "i1"), None) == 3.5` (flip), `pick_spread_for("i1", "i1", None, -3.5) == -3.5` (home fav via pool line), `pick_spread_for("i2", "i1", None, -3.5) == 3.5` (away dog via pool line); LOCKED standing entry skipped; MISSING → (None, 'MISSING').
- [ ] **Step 2:** `.venv/bin/pytest tests/test_mapper.py -q` — FAIL.
- [ ] **Step 3:** Implement `mapper.py` (pure; `zoneinfo.ZoneInfo("America/New_York")`; tolerate absent optional fields with `.get`).
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass.
- [ ] **Step 5:** `git add -A && git commit -m "feat: CBS→DB mapper with spread perspective + MNF + week divergence handling"`

---

### Task 6: Sync CLI + reconciliation

**Files:**
- Create: `$CANON/app/sync/run.py`, `$CANON/app/sync/reconcile.py`, `$CANON/app/sync/__main__.py`, `$CANON/tests/test_sync.py`, `$CANON/tests/test_reconcile.py`

**Interfaces:**
- Consumes: CBSClient (T3), queries (T4), mapper (T5), db (T2).
- Produces:

```python
# app/sync/reconcile.py
def reconcile_week(conn, week_id: int, period_scores: dict[str, int]) -> list[str]
# compares SELECT count of picks result='CORRECT' per player that week vs CBS periodScore
# (keyed by cbs_entry_id); returns human-readable mismatch strings, [] = clean.

# app/sync/run.py
def run_sync(settings, client: CBSClient | None = None, backfill_all: bool = False) -> dict
# returns {"ok": bool, "weeks": [ordinals], "games": int, "picks": int,
#          "reconcile_ok": bool, "mismatches": [...], "error": str | None}
```

- Sync algorithm (implement exactly): open db + migrate → POOL_META (store meta pool_name/season_year) → POOL_PERIODS → upsert weeks → choose target weeks: `backfill_all` → all; else weeks with status='open' plus any week whose id > last final id (i.e. current) → per target week: WEEK_EVENTS → upsert games (compute is_monday_night; status final when scores present) → WEEK_STANDINGS → upsert players/picks/tb_answers (build `slot_to_event`/`item_to_side` from the events payload) → ENTRY_PICKS → update `pick_spread` via `pick_spread_for` → `reconcile_week` with `period_scores` → mark week final iff all its games final → write `sync_runs` row + meta `last_sync_at` (UTC ISO). All DB writes for a week happen in ONE transaction committed only after that week's queries all succeeded. `CBSAuthError` anywhere → rollback, `sync_runs` row with error='AUTH_EXPIRED', re-raise.
- CLI (`__main__.py`): `python -m app.sync [--all]` → prints one JSON line (the run_sync dict); exit 0 ok, **2 on CBSAuthError**, 1 anything else. (Exit 2 is the contract the pickem-sync skill alerts on — Task 16.)

- [ ] **Step 1:** Write `tests/test_reconcile.py` (build_season fixture: 2 players, 1 week, known corrects; matching period_scores → [], off-by-one → 1 mismatch naming the player) and `tests/test_sync.py`: a `FakeClient` whose `query(gql, variables)` returns the Task-4 fixture payload matching the query constant (compare `gql is queries.POOL_META` etc.); assert run_sync populates weeks/games/players/picks/tb_answers, sync_runs has ok=1, second run is idempotent (same row counts), and a FakeClient raising CBSAuthError on WEEK_STANDINGS leaves zero picks rows (transaction rollback) and records error='AUTH_EXPIRED'.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_sync.py tests/test_reconcile.py -q` — FAIL.
- [ ] **Step 3:** Implement all three files. Upserts via `INSERT ... ON CONFLICT ... DO UPDATE`.
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass (whole suite).
- [ ] **Step 5:** `git add -A && git commit -m "feat: sync engine with transactional weeks, reconcile gate, AUTH_EXPIRED exit contract"`

---

### Task 7: CHECKPOINT — live backfill against the real pool

No new code files. This gate validates everything upstream before the engine is built on it.

- [ ] **Step 1:** `cd $CANON && .venv/bin/python -m app.sync --all` — expect exit 0, JSON line with `ok: true`.
- [ ] **Step 2:** Inspect: `sqlite3 volumes/pickem.db "SELECT count(*) FROM players; SELECT id, nfl_week, ncaaf_week, status FROM weeks; SELECT sport, count(*) FROM games GROUP BY sport; SELECT result, count(*) FROM picks GROUP BY result;"` — expect 81 players; completed week(s) final; both sports present; CORRECT/INCORRECT counts plausible.
- [ ] **Step 3:** Cross-check 3 players' completed-week scores against the CBS standings page numbers (operator provides or confirms via the site) AND assert `reconcile_ok: true` in the sync output. Any mismatch → STOP, fix mapper/sync, re-run. Do not proceed to Task 8 with a dirty reconcile.
- [ ] **Step 4:** `git commit --allow-empty -m "checkpoint: live backfill reconciles clean vs CBS (81 players)"`

---

### Task 8: Weekly tiebreak cascade

**Files:**
- Create: `$CANON/app/scoring/__init__.py`, `$CANON/app/scoring/tiebreak.py`, `$CANON/tests/test_tiebreak.py`

**Interfaces:**
- Produces:

```python
def resolve_weekly_tie(
    week: int,
    tied: list[int],                                # player ids, all with equal max correct in `week`
    correct_by_week: dict[int, dict[int, int]],     # week -> {player_id: correct_count}
    tb_error_by_week: dict[int, dict[int, float]],  # week -> {player_id: abs(guess - actual)}; absent = no answer
    last_completed_week: int,
    season_complete: bool,
) -> dict
# {"winners": [ids], "provisional": bool, "resolution": str}
# Cascade at week w (start w=week): (1) min tb_error at w (absent answer = +inf);
# single survivor → done, resolution=f"tb@{w}". (2) still tied: if w+1 > last_completed_week:
#   season_complete → winners=survivors, provisional=False, resolution="split"
#   else → winners=survivors, provisional=True, resolution=f"pending@{w+1}"
# (3) else filter by max correct at w+1 (resolution=f"correct@{w+1}"), then tb at w+1, loop.
```

- [ ] **Step 1:** Write `tests/test_tiebreak.py`: (a) tb resolves outright (errors 3 vs 5); (b) missing tb answer loses to any answer; (c) equal tb → next week's correct decides; (d) equal tb + equal next correct → next week's tb decides; (e) cascade past `last_completed_week` mid-season → provisional=True, both winners listed; (f) same at season_complete → provisional=False split; (g) singleton `tied` short-circuits.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_tiebreak.py -q` — FAIL.
- [ ] **Step 3:** Implement (≈35 lines, a while-loop; no DB access — pure).
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass.
- [ ] **Step 5:** `git add -A && git commit -m "feat: cascading weekly tiebreak resolver (abs diff, next-week chain, split at season end)"`

---

### Task 9: Prize engine

**Files:**
- Create: `$CANON/app/scoring/engine.py`, `$CANON/tests/test_engine.py`

**Interfaces:**
- Consumes: tiebreak (T8), db schema (T2), prize constants (T1).
- Produces (each returns JSON-ready structures; `conn` first arg):

```python
def weekly_correct_map(conn) -> dict[int, dict[int, int]]     # week -> player -> CORRECT count (completed weeks only)
def tb_error_map(conn) -> dict[int, dict[int, float]]         # abs(answer - actual MNF total) per completed week;
                                                              # actual = home+away of the week's tiebreaker_order game
def weekly_results(conn, season_final_week: int) -> list[dict]
# per completed week: {"week", "max_correct", "winners": [{"id","name"}], "provisional", "resolution", "prize_each": float}
def season_leaderboard(conn) -> list[dict]
# [{"rank", "id", "name", "correct", "graded", "missed", "money_projected": float}] — rank by correct desc;
# ties share a rank; money_projected = SEASON_PRIZES pooled-and-split across tied ranks (e.g. two tied at 1 → 650 each)
def brutus_leaderboard(conn) -> list[dict]                    # NCAAF correct desc: {"rank","id","name","correct"}
def bottom_race(conn) -> list[dict]                           # correct asc; {"rank","id","name","correct","eligible": bool}
                                                              # eligible = zero MISSING picks across all completed weeks
def underdog_leaderboard(conn) -> list[dict]
# picks with pick_spread > 0 and result in (CORRECT, INCORRECT): {"rank","id","name","dog_correct","dog_picks","pct","eligible": dog_picks >= UNDERDOG_MIN_PICKS}
# rank eligible players first by pct desc then dog_picks desc; ineligible listed after, unranked (rank None)
def monday_lights_leaderboard(conn) -> list[dict]             # CORRECT count over games where is_monday_night=1: {"rank","id","name","correct"}
def prize_summary(conn, season_final_week: int) -> dict
# {"weekly_won": {player_id: float}  (resolved weeks only, split when resolution=="split"),
#  "projected": {player_id: float}   (season + side prizes if season ended today, ties split),
#  "total_pot": 4050}
```

- [ ] **Step 1:** Write `tests/test_engine.py` on a purpose-built `build_season` fixture (3 weeks × 4 games (2 NFL incl. 1 MNF-flagged tb game, 2 NCAAF) × 5 players) with hand-computed expectations: outright weekly winner (w1); tb-resolved winner (w2); provisional tie (w3 = last completed, cascade exhausted); season ranks with a 2-way tie at 1st → 650 each projected; brutus counts NCAAF only; bottom: the worst player ineligible via one MISSING pick, next-worst eligible; underdog pct math + `eligible` False below threshold (use a tiny threshold via monkeypatching `UNDERDOG_MIN_PICKS`? NO — engine must read the constant through `app.config`; monkeypatch `app.config.UNDERDOG_MIN_PICKS` to 3 in the test); MNL counts only the MNF game; prize_summary weekly_won excludes the provisional week.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_engine.py -q` — FAIL.
- [ ] **Step 3:** Implement `engine.py`. SQL aggregation + small Python; `weekly_results` wires `resolve_weekly_tie` with `season_complete = (last completed week id == season_final_week)`.
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass.
- [ ] **Step 5:** `git add -A && git commit -m "feat: prize engine — six races, split math, provisional weekly states"`

---

### Task 10: Player stats, comparison, league analytics

**Files:**
- Create: `$CANON/app/scoring/stats.py`, `$CANON/tests/test_stats.py`

**Interfaces:**
- Produces:

```python
def player_stats(conn, player_id: int) -> dict | None   # None if unknown id
# {"id","name","record": {"correct","incorrect","missed","pct"},
#  "by_sport": {"NFL": {"correct","incorrect","pct"}, "NCAAF": {...}},
#  "dog_fav": {"dog": {"picks","correct","pct"}, "fav": {...}},   # dog: pick_spread>0, fav: pick_spread<0
#  "side_lean": {"home","away"},                                   # counts of picked_team
#  "top_teams": [{"team","picks","correct"}] (top 5 by picks),     # team = picked side's name
#  "streaks": {"current","longest"},                               # CORRECT streaks in kickoff order (graded picks only)
#  "weekly_correct": [{"week","correct","rank"}],                  # rank = weekly rank by correct
#  "consensus": {"with": {"picks","correct"}, "against": {...}},   # majority side per game among graded picks; ties (50/50) excluded
#  "mnf": {"correct","picks"}, "tiebreaker": {"avg_error": float | None}}
def compare_players(conn, ids: list[int]) -> dict
# {"players": [player_stats(...) per id], "head_to_head": {"weeks_won": {id: count}}}
# weeks_won: among the compared ids only, who had strictly-most corrects that week (ties → no one)
def league_analytics(conn) -> dict
# {"weeks": [{"week","avg_correct","max_correct"}],
#  "most_trusted": [{"team","pick_rate","cover_rate"}] (top 10 by pick_rate, graded games),
#  "upsets": [{"week","game","pct_correct"}] (10 lowest pct_correct graded games; "game" = "AWAY @ HOME"),
#  "all_favorites_benchmark": [{"week","correct"}]}   # correct = games where the favorite (pool_spread side) covered
```

- [ ] **Step 1:** Write `tests/test_stats.py` on the Task-9 fixture: hand-verified record/pct for one player; dog/fav split matches pick_spread signs; consensus: construct one game 3-vs-2 → majority side known; streak across weeks in kickoff order; compare_players weeks_won; league upsets ordering; unknown player → None.
- [ ] **Step 2:** `.venv/bin/pytest tests/test_stats.py -q` — FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass.
- [ ] **Step 5:** `git add -A && git commit -m "feat: player tendencies, head-to-head compare, league analytics"`

---

### Task 11: Public API + app assembly

**Files:**
- Create: `$CANON/app/api.py`, `$CANON/app/main.py`, `$CANON/tests/test_api.py`

**Interfaces:**
- Consumes: engine (T9), stats (T10), db (T2), config (T1).
- Produces FastAPI app `app.main:app` with:
  - `GET /healthz` → `{"ok": true, "db": true}` 200 (503 if db unreadable)
  - `GET /api/meta` → `{"pool_name", "season_year", "last_sync_at", "stale": bool}` (stale = last_sync_at older than 48h)
  - `GET /api/leaderboards` → `{"season": season_leaderboard(), "weekly": weekly_results(), "brutus": ..., "bottom": ..., "underdog": ..., "monday": ..., "prizes": prize_summary()}`
  - `GET /api/players` → `[{"id","name"}]` sorted by name
  - `GET /api/players/{id}` → `player_stats` + that player's pick history: `{"stats": ..., "history": [{"week","game","sport","picked","spread","result"}]}` (404 unknown)
  - `GET /api/compare?players=1,2,3` → `compare_players` (400 unless 2–4 valid ids)
  - `GET /api/analytics` → `league_analytics`
  - `GET /api/internal/sync-status` (admin) → last 20 `sync_runs` rows
  - Admin auth dependency `require_admin`: header `X-Admin-Token` must equal `settings.admin_token`; 403 otherwise; **503 if `settings.admin_token` is empty** (feature disabled).
  - `app.main` mounts `api` routers, serves `frontend/dist` via `StaticFiles(html=True)` at `/` when the directory exists, and opens one sqlite connection per request via dependency `get_conn` (closes on teardown).
- Produces: `get_conn` and `require_admin` importable from `app.api` (Task 12 reuses both).

- [ ] **Step 1:** Write `tests/test_api.py` with `fastapi.testclient.TestClient` over a fixture-built DB (point `PICKEM_DATA_DIR` at tmp_path via monkeypatch before importing app; build_season first): healthz 200; leaderboards contains all 7 keys; player 404; compare validates count; sync-status 403 wrong token / 503 no token configured / 200 right token; meta stale=True (no last_sync_at).
- [ ] **Step 2:** `.venv/bin/pytest tests/test_api.py -q` — FAIL.
- [ ] **Step 3:** Implement `api.py` + `main.py`.
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass. Also boot it once: `PICKEM_DATA_DIR=volumes .venv/bin/uvicorn app.main:app --port 8793 &`; `curl -s localhost:8793/api/leaderboards | head -c 400`; kill it. Real backfilled data should render.
- [ ] **Step 5:** `git add -A && git commit -m "feat: public API + admin sync-status + app assembly"`

---

### Task 12: AI analysis service + internal endpoints

**Files:**
- Create: `$CANON/app/analysis/__init__.py`, `$CANON/app/analysis/service.py`, `$CANON/tests/test_analysis.py`
- Modify: `$CANON/app/api.py` (add 3 routes; import from `app.analysis.service`)

**Interfaces:**
- Consumes: `get_conn`, `require_admin` (T11); analyses/analysis_requests tables (T2); Settings (T1).
- Produces in `service.py`:

```python
GLOBAL_DAILY_CAP = 24
PER_IP_DAILY_CAP = 3

def request_analysis(conn, settings, player_id: int, client_ip: str) -> dict
# returns {"status": "ready", "analysis": {...}} on fresh cache hit (same through_week = latest completed week);
# {"status": "generating"} if a row is already generating for (player, through_week);
# {"status": "rate_limited", "retry": "tomorrow"} when caps hit (ip hashed sha256 before storing);
# else inserts analyses row status='generating', logs analysis_requests, enqueues, returns {"status": "generating"}.
# Enqueue: settings.fake_analysis → immediately store_analysis(canned markdown, model="fake").
# Otherwise POST {settings.gateway_url}/api/jobs json={"description": f"pickem analysis player={player_id} through_week={w}",
#   "kind": "pickem-analysis", "payload": {"player_id": player_id, "through_week": w}}
#   headers={"Authorization": f"Bearer {settings.gateway_token}"} (httpx, 10s timeout).
# Gateway unreachable/non-2xx → mark row status='error', return {"status": "error", "detail": "generation lane unavailable"}.

def store_analysis(conn, player_id: int, through_week: int, markdown: str, model: str) -> None   # upsert, status='ready'
def get_analysis(conn, player_id: int) -> dict | None    # latest ready/generating row for player
```

- Produces routes in `api.py`: `GET /api/players/{id}/analysis` (200 with row or `{"status":"none"}`), `POST /api/players/{id}/analysis` (calls `request_analysis` with `request.client.host`), `POST /api/internal/analyses` (admin; body `{"player_id","through_week","markdown","model"}` → `store_analysis`) — this is the callback the pickem-analysis skill hits.

- [ ] **Step 1:** Write `tests/test_analysis.py`: fake_analysis mode end-to-end (POST → ready with markdown); cache hit returns ready without new request row; 4th request from same ip hash → rate_limited; 25th global → rate_limited; gateway-down path (settings with fake_analysis=False, gateway_url pointing at a closed port) → status error; internal POST with admin token stores and flips generating→ready.
- [ ] **Step 2:** Run — FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** `.venv/bin/pytest -q` — pass.
- [ ] **Step 5:** `git add -A && git commit -m "feat: AI analysis lane — cache, rate limits, gateway enqueue, internal callback"`

---

### Task 13: Frontend shell + Leaderboards page

**Files:**
- Create: `$CANON/frontend/` via `npm create vite@latest frontend -- --template react-ts`, then `src/api.ts`, `src/App.tsx`, `src/pages/Leaderboards.tsx`, `src/components/{PrizeTable.tsx,Tabs.tsx}`, `src/theme.css`
- Modify: `frontend/vite.config.ts` (dev proxy `/api` + `/healthz` → `http://localhost:8793`)

**Interfaces:**
- Consumes: `/api/meta`, `/api/leaderboards` (T11 shapes).
- Produces: `src/api.ts` typed fetchers used by Task 14: `getMeta()`, `getLeaderboards()`, `getPlayers()`, `getPlayer(id)`, `getCompare(ids: number[])`, `getAnalytics()`, `getAnalysis(id)`, `postAnalysis(id)` — thin `fetch` wrappers returning parsed JSON, throwing on non-2xx.
- Produces: `App.tsx` with react-router routes `/` (Leaderboards), `/player/:id`, `/compare`, `/analytics`; header shows `meta.pool_name` + "through last sync" stamp + nav; `theme.css` dark palette (bg `#0e1420`, panel `#182238`, accent `#4ea1ff`, gold `#e8b93c` for money), system font stack, table styles.
- Leaderboards page: `Tabs` component over the six races + Money tab; `PrizeTable` renders rank/name/metric/money columns from props (`rows`, `columns` config); weekly tab shows winner chips with a "provisional" badge when `provisional` and prize amounts; player names link to `/player/:id`.

- [ ] **Step 1:** Scaffold: `cd $CANON && npm create vite@latest frontend -- --template react-ts && cd frontend && npm install && npm install react-router-dom recharts`.
- [ ] **Step 2:** Implement the files above (delete Vite demo cruft). Keep components dumb: fetch in pages via `useEffect`, loading + error states (`<p className="err">backend unreachable</p>`).
- [ ] **Step 3:** Verify against the REAL backfilled backend: run uvicorn (as in T11 step 4) + `npm run dev`; open the printed URL; leaderboards render 81 real players; tabs all switch; no console errors.
- [ ] **Step 4:** `npm run build` — succeeds; then re-run backend and confirm `curl -s localhost:8793/ | grep -o '<title>[^<]*'` serves the built SPA (StaticFiles path from T11 = `frontend/dist`).
- [ ] **Step 5:** `git add -A && git commit -m "feat: SPA shell + six-race leaderboards on live data"`

---

### Task 14: Player, Compare, Analytics pages + AI button

**Files:**
- Create: `frontend/src/pages/{Player.tsx,Compare.tsx,Analytics.tsx}`, `frontend/src/components/{StatGrid.tsx,PickHistory.tsx,AnalysisPanel.tsx,TrendChart.tsx}`

**Interfaces:**
- Consumes: `api.ts` fetchers (T13), API shapes (T11/T12).
- Produces:
  - Player page: `StatGrid` (record, by-sport, dog/fav, side lean, consensus, MNF, tiebreaker avg error as labeled stat cards), `TrendChart` (Recharts `LineChart` of `weekly_correct[].rank` inverted-Y = rank trajectory), `PickHistory` (table grouped by week: game, picked side + spread shown like `DAL −3.5`, result color-coded), `AnalysisPanel`: shows existing analysis markdown (render with a 15-line markdown-to-JSX helper — headings/bold/lists only, no dependency), "Generate AI analysis" button → `postAnalysis(id)` → status handling: generating → poll `getAnalysis` every 5s (max 3 min) → ready renders; rate_limited/error → friendly message.
  - Compare page: multi-select (2–4) from `getPlayers()`, then side-by-side `StatGrid` columns + weeks_won row.
  - Analytics page: weekly difficulty bar chart (`avg_correct` per week), most-trusted table, upsets table, all-favorites benchmark line vs weekly average.

- [ ] **Step 1:** Implement all files.
- [ ] **Step 2:** Manual verify on live data: player page renders a real player with history + charts; AI button in `PICKEM_FAKE_ANALYSIS=1` backend returns canned markdown and renders it; compare 3 players; analytics tables populated.
- [ ] **Step 3:** `npm run build` — clean (tsc passes = the type gate).
- [ ] **Step 4:** `git add -A && git commit -m "feat: player/compare/analytics pages + AI analysis panel"`

---

### Task 15: manifest, project docs, delivery contract

**Files:**
- Create: `$CANON/manifest.yml`, `$CANON/CLAUDE.md`, `$CANON/.context/CONTEXT.md`, `$CANON/.context/CHANGELOG.md`, `$CANON/run.sh`

**Interfaces:**
- Consumes: ai-server manifest schema (`.context/modules/hosting/CONTEXT.md` in ai-server repo).
- Produces `manifest.yml` (exact):

```yaml
slug: pickem
name: Arlington Degenerates Pick'em
mission: "Public dashboard for the CBS pick'em league: prize leaderboards, pick analytics, player comparison, AI analysis"
type: service
subdomain: pickem
port: 8793
healthcheck: /healthz
start_command: "set -a && [ -f .env ] && source .env; set +a; .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8793"
web_strategy: native-web
platforms:
  primary: web
  web: native
env_required:
  - PICKEM_DATA_DIR
  - PICKEM_ADMIN_TOKEN
created_at: "2026-09-09"
git:
  repo: "https://github.com/Piserchia/pickem"
  branch: main
delivery:
  topology: dev-repo
  dev_repo: ~/Documents/repos/pickem
  runtime_clone: pull-only
  branch: main
  deployable: true
  env_files: [".env"]
  deploy:
    skill: project-redeploy
    autonomy: gated-auto
    gates:
      - kind: test
        cmd: ".venv/bin/pytest -q"
      - kind: build
        cmd: "cd frontend && npm ci && npm run build"
        when_paths: ["frontend/**"]
      - kind: healthcheck
        path: /healthz
        expect: 200
    services: [pickem]
```

- `CLAUDE.md`: rules — read `.context/CONTEXT.md` first; never touch `.secrets/` or commit cookies; CBS traffic constraints (gentle, errors[] gate); data dir is external (`PICKEM_DATA_DIR`); frontend changes need `npm run build`; append `.context/CHANGELOG.md` every session.
- `.context/CONTEXT.md`: the five standard sections (Mission, Platforms, Web Serving, Architecture — module map from this plan, Status). `.context/CHANGELOG.md`: bootstrap entry.
- `run.sh`: dev convenience — venv check, `uvicorn app.main:app --reload --port 8793`.

- [ ] **Step 1:** Write all five files.
- [ ] **Step 2:** Validate manifest from the ai-server repo: `cd ~/Documents/repos/ai-server && pipenv run python -c "from src.registry.manifest import load; m=load('/Users/alfredbot.ai.butler/Documents/repos/pickem/manifest.yml'); print(m)"` — parses, delivery block recognized. (If `load` has a different name, check `src/registry/manifest.py` — use its public loader.)
- [ ] **Step 3:** `git add -A && git commit -m "feat: manifest with gated-auto delivery contract + project docs" && git push origin main`

---

### Task 16: ai-server skills, registries, schedule row

**Files (ai-server repo — INV-13 applies):**
- Create: `skills/pickem-sync/SKILL.md`, `skills/pickem-analysis/SKILL.md`
- Modify: `.context/SKILLS_REGISTRY.md` (2 rows), `scripts/seed-schedules.sh` (1 upsert line), `projects/_ports.yml` (`8793: pickem`), `.context/PROJECTS_REGISTRY.md` (row + short blurb)

**Interfaces:**
- Consumes: sync CLI exit contract (T6: exit 2 = AUTH_EXPIRED), internal analyses endpoint (T12), gateway job lane.
- Produces `skills/pickem-sync/SKILL.md` — frontmatter: `name: pickem-sync`, `description: Run the pickem CBS sync and report the result`, `model: claude-sonnet-4-6`, `effort: low`, `permission_mode: acceptEdits`, `required_tools: [Bash, Read]`, `max_turns: 15`, `isolation: none`, `tags: [pickem, sync]`. Body (system prompt): cd to `$SERVER_ROOT/projects/pickem`; run `.venv/bin/python -m app.sync`; exit 0 → summarize the JSON (weeks, picks, reconcile_ok — if reconcile_ok false, flag prominently); **exit 2 → the summary MUST start with "⚠️ PICKEM AUTH EXPIRED"** and instruct the owner to run `scripts/export_cbs_cookies.py` on their machine and copy the file to `$SERVER_ROOT/volumes/pickem/cbs_cookie_header.txt`; exit 1 → quote the error, check `sync_runs` via sqlite3 for context. Never edit code (report instead).
- Produces `skills/pickem-analysis/SKILL.md` — frontmatter: `model: claude-sonnet-4-6`, `effort: medium`, `permission_mode: acceptEdits`, `required_tools: [Bash, Read]`, `max_turns: 15`, `isolation: none`. Body: payload gives `player_id`, `through_week`; `curl -s localhost:8793/api/players/{player_id}` and `/api/leaderboards`; write a ~300-word fun-but-sharp markdown analysis (tendencies, dog/fav profile, consensus contrarianism, prize outlook, one playful roast line — names are league members, keep it good-natured); read `PICKEM_ADMIN_TOKEN` from `$SERVER_ROOT/projects/pickem/.env`; POST it to `localhost:8793/api/internal/analyses` with header `X-Admin-Token` and body `{"player_id", "through_week", "markdown", "model": "<your model id>"}`; verify 200.
- Produces seed line (after the atlas block in `seed-schedules.sh`):

```bash
upsert 'pickem-sync' '0 9 * * 0,1,2,5' 'pickem-sync' 'Pickem CBS sync (Sun/Mon/Tue/Fri post-slate)' '{"project_slug":"pickem"}'
```

- [ ] **Step 1:** `cd ~/Documents/repos/ai-server && git fetch origin && git merge origin/main`.
- [ ] **Step 2:** Write both skills + registry rows + ports line + seed line.
- [ ] **Step 3:** Gates: `python scripts/lint_docs.py` and `pipenv run pytest -q` — green.
- [ ] **Step 4:** Code-review agent over the diff (INV-13) — LGTM required; fix findings.
- [ ] **Step 5:** `git add -A && git commit -m "feat(skills): pickem-sync + pickem-analysis, schedule row, registries (port 8793)"` then fetch/merge again and `git push origin main`.

---

### Task 17: Production deploy + registration + first prod sync

**Files:** none new in git (prod provisioning). `PROD="$HOME/Library/Application Support/ai-server"`.

- [ ] **Step 1:** Runtime clone + prime: `git clone ~/Documents/repos/pickem "$PROD/projects/pickem"` then in the clone: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` and `cd frontend && npm ci && npm run build`.
- [ ] **Step 2:** Data + secrets: `mkdir -p "$PROD/volumes/pickem"`; copy `~/Documents/repos/pickem/.secrets/cbs_cookie_header.txt` → `"$PROD/volumes/pickem/"` (chmod 600). Write `"$PROD/projects/pickem/.env"` (gitignored): `PICKEM_DATA_DIR="$PROD/volumes/pickem"`, `PICKEM_COOKIE_FILE="$PROD/volumes/pickem/cbs_cookie_header.txt"`, `PICKEM_ADMIN_TOKEN=$(openssl rand -hex 24)`, `PICKEM_GATEWAY_URL=http://127.0.0.1:8080`, `PICKEM_GATEWAY_TOKEN=<WEB_AUTH_TOKEN from "$PROD/.env">`. Mirror a dev copy of `.env` in $CANON with dev paths (it's gitignored; `.env.example` documents it).
- [ ] **Step 3:** First prod backfill BEFORE hosting: `cd "$PROD/projects/pickem" && set -a && source .env && set +a && .venv/bin/python -m app.sync --all` — exit 0, reconcile_ok true.
- [ ] **Step 4:** Register + deploy ai-server side on prod: `cd "$PROD" && git pull --ff-only` (brings Task-16 commit; or run the `server-deploy` skill), `bash scripts/seed-schedules.sh`, `bash scripts/register-project.sh pickem`.
- [ ] **Step 5:** Verify, in order: `curl -s localhost:8793/healthz` → `{"ok":true...}`; `curl -s https://pickem.chrispiserchia.com/healthz` (from the public internet path) → 200; open `https://pickem.chrispiserchia.com` — leaderboards render real data; `psql assistant -c "SELECT name, cron_expression FROM schedules WHERE name='pickem-sync';"` → row present; trigger one AI analysis end-to-end on the live site for one player (owner's own entry is the polite guinea pig) and see it render.
- [ ] **Step 6:** `launchctl list | grep pickem` shows the service; check `"$PROD/volumes/logs/"` for its log file; confirm healthcheck-all picks it up on the next 5-min tick.

---

### Task 18: Full-diff review sweep + writeback

- [ ] **Step 1:** Adversarial review of the pickem repo (fresh reviewer, full tree): correctness of spread-perspective math, tiebreak cascade off-by-ones, SQL injection surface (all queries parameterized?), rate-limiter bypass, secrets hygiene (`git log -p | grep -i cookie` clean). Fix + commit findings.
- [ ] **Step 2:** ai-server writeback: update `.context/PROJECTS_REGISTRY.md` row status if anything changed during deploy; INDEX.md addition row updated from "build in progress" → live; `CHANGELOG.md` entries for any ai-server modules touched; run `python scripts/lint_docs.py` + `pipenv run pytest -q`; commit + push (INV-13 gates as in Task 16).
- [ ] **Step 3:** Update `$CANON/.context/CHANGELOG.md` + CONTEXT Status section to reflect what shipped; commit + push.
- [ ] **Step 4:** Report to owner: URL, what's live, the 4 sync slots, the cookie-refresh runbook (script + prod copy path), and the one thing to watch (first AUTH_EXPIRED alert).

---

## Self-Review Notes

- **Spec coverage:** ingestion incl. fallback tiers — the SSR fallback (`ssr_fallback.py`) is deliberately DEFERRED from v1 scope: the manual-import escape hatch it backstops is admin-only and the reconcile gate catches drift; if CBS breaks the GraphQL shape mid-season, that is the moment to build the fallback against the real breakage rather than speculatively now. `/api/internal/import` is likewise deferred (manual imports can go through sqlite3 directly with commissioner assistance). Both are recorded as Status "planned" items in Task 15's CONTEXT.md. Everything else in the spec maps: T1–T7 ingestion, T8–T10 engine/analytics, T11–T14 site, T12+T16 AI lane, T15–T17 ops/hosting, T18 review.
- **Type consistency check:** `resolve_weekly_tie` signature matches its T9 call site; `pick_spread_for` argument order consistent between T5 definition and tests; `require_admin`/`get_conn` shared T11→T12; api.ts fetcher names match T13 definition and T14 usage; exit-code 2 contract consistent T6→T16.
- **Fixtures over mocks:** T5/T6 test against REAL captured pool data (pseudonymized), which is what de-risks the unofficial API more than any synthetic mock could.
