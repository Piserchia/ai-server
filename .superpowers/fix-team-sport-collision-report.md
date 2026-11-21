# fix/team-sport-collision — work report

Repo: `/Users/alfredbot.ai.butler/Documents/repos/pickem`
Branch: `fix/team-sport-collision` (off `main`)
Commits:
- `5bf907b` — `fix(stats): key team rows by (sport, team), not the bare abbreviation`
- `9230ebd` — `refactor(frontend): remove the pick-history section from the player page`

Both commits end with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## Change 1 — team rows keyed by (sport, team)

### What was edited

- `app/scoring/stats.py`
  - Module docstring (the "Conventions" bullet list, originally ending at the
    `top_teams` paragraph around line 21): appended a sentence that
    `top_teams`/`most_trusted` key on `(sport, team)` because CBS
    abbreviations are only unique per sport (HOU example).
  - `player_stats` docstring (~line 290): added a paragraph naming the same
    keying rule.
  - `player_stats` loop (~line 344-351): added `team_sport = pick["sport"]`;
    `teams.setdefault` now keys on `(team_sport, team)` and the row dict
    gains `"sport": team_sport`.
  - `top_teams` sort key (~line 402): `(-picks, -correct, team)` →
    `(-picks, -correct, team, sport)`.
  - `league_analytics` docstring (~line 489): added a paragraph naming the
    same rule for `most_trusted`.
  - `league_analytics` teams aggregation (~line 530-541): `teams.setdefault`
    now keys on `(game["sport"], team)`; row dict gains `"sport"`.
  - `trusted` sort/shape (~line 558-572): intermediate dict gains `"sport"`;
    sort key `(-pick_rate, -picks, team)` → `(-pick_rate, -picks, team, sport)`.
  - `most_trusted` output list (~line 610-617): each emitted row now includes
    `"sport": row["sport"]`.
- `tests/test_stats.py`
  - `test_player_stats_carries_every_documented_section` (~line 60): row
    shape set now includes `"sport"`.
  - `test_side_lean_and_top_teams_count_made_picks` (~line 121): expected
    rows gained `sport` (DAL→NFL, LSU/ND/OSU/OU→NCAAF, derived from the
    shared `ENGINE_SEASON` fixture in `tests/conftest.py`).
  - `test_pending_picks_count_as_lean_but_never_as_a_rate` (~line 282):
    expected rows gained `"sport": "NFL"` (all four teams are NFL in
    `_in_progress_season`).
  - `test_most_trusted_teams_rank_by_pick_rate` (~line 399): tuple comparison
    extended to include `sport` for every team.
  - `test_a_game_nobody_got_right_still_knows_which_side_covered` (~line 466):
    expected `most_trusted` rows gained `"sport": "NFL"`.
  - New regression test `test_the_same_abbreviation_in_two_sports_is_two_team_rows`
    (inserted after `test_top_teams_rank_by_volume_then_hits_then_name`,
    ~line 160): builds a one-week fixture with an NCAAF game (HOU home,
    covers) and an NFL game (HOU away, does not cover); player "Hal" picks
    HOU in both. Asserts `top_teams` has two distinct rows
    (`{"team":"HOU","sport":"NCAAF","picks":1,"graded":1,"correct":1}` and
    `{"team":"HOU","sport":"NFL","picks":1,"graded":1,"correct":0}`), that
    their `picks` sum to 2 (Hal's total picks on the abbreviation), and the
    parallel `most_trusted` assertion (two HOU rows, NCAAF pick_rate 1.0/
    cover_rate 1.0, NFL pick_rate 1.0/cover_rate 0.0).
  - `tests/test_api.py` line ~321 (`test_analytics_returns_expected_shape`):
    checked — it only asserts the analytics *top-level* key set
    (`weeks`/`most_trusted`/`upsets`/...), not row shape, so it was
    unaffected and needed no change.
- Frontend (additive `sport` field + UI + row-key fix):
  - `frontend/src/api.ts`: `TopTeam` and `TrustedTeam` interfaces gained
    `sport: string` with a doc comment on each explaining the HOU collision.
  - `frontend/src/pages/Player.tsx`: `TEAM_COLUMNS` gained a `{key: "sport",
    label: "Sport", ...}` column right after `team`; `rowKey` on the
    `PrizeTable` call changed from `row.team` to `` `${row.sport}-${row.team}` ``
    — this was not explicitly asked for in the brief's wording but is
    load-bearing: `rowKey` becomes the React key, and once two sports can
    legitimately share an abbreviation, the bare team name is no longer
    unique.
  - `frontend/src/pages/Analytics.tsx`: same two changes for
    `TRUSTED_COLUMNS` / its `PrizeTable` call.

### TDD evidence

Before adding the `sport` key (fixing only the test file, code still old),
`.venv/bin/pytest -q tests/test_stats.py` failed with 4 red tests:

```
FAILED tests/test_stats.py::test_player_stats_carries_every_documented_section - assert False
FAILED tests/test_stats.py::test_side_lean_and_top_teams_count_made_picks - AssertionError: assert [{'team': 'DA...ded': 1, ...}] == [{'team': 'DA...'c...
FAILED tests/test_stats.py::test_pending_picks_count_as_lean_but_never_as_a_rate - AssertionError: assert [{'team': 'DA...ded': 0, ...}] == [{'team': 'DA...'c...
FAILED tests/test_stats.py::test_a_game_nobody_got_right_still_knows_which_side_covered - AssertionError: assert [{'team': 'NY...r_rate': 1.0}] == [{'team': 'NY...r_...
4 failed, 60 passed in 0.45s
```

(Diff detail from `test_side_lean_and_top_teams_count_made_picks`: expected
dict had no `sport` key while the actual row already carried
`{'team': 'DAL', 'sport': 'NFL', ...}` — confirming the production code had
already been changed and the test fixtures were the stale half, i.e. this
captured the test-update step of TDD rather than a pre-code-change red bar.
The actual red-before-green sequence that drove the implementation was: ran
`player_stats`/`league_analytics` unmodified against the new regression
test first — `test_the_same_abbreviation_in_two_sports_is_two_team_rows`
failed with `KeyError: 'sport'` / merged single-row output before the
`stats.py` edits landed, then passed once the (sport, team) keying was
added.)

After fixing both `stats.py` and the four pinned assertions, and adding the
new regression test:

```
tests/test_stats.py::test_the_same_abbreviation_in_two_sports_is_two_team_rows PASSED [100%]
1 passed, 64 deselected in 0.06s
```

Full stats-file run after the fix: `64 passed`.

### Full suite / build tails (final branch state, after both commits)

```
$ .venv/bin/pytest -q
546 passed, 7 deselected, 2 warnings in 6.79s
```

(7 deselected = `live`-marked tests, never run per project convention —
`pytest.ini`'s `addopts = -m "not live"`.)

```
$ cd frontend && npm run lint
> oxlint
src/pages/PlayerCharts.tsx:85:61: warning react(set-state-in-effect): ...
src/components/ChartPrompt.tsx:24:17: warning react(only-export-components): ...
src/components/ChartPrompt.tsx:64:7: warning react-hooks(exhaustive-deps): ...
src/components/ChartPrompt.tsx:46:9: warning react-hooks(exhaustive-deps): ...
(exit 0 — all four warnings are pre-existing, in files untouched by this work)
```

```
$ npm run build
> tsc -b && vite build
✓ 617 modules transformed.
dist/assets/Player-rqX-Dam6.js   8.86 kB │ gzip: 3.46 kB
...
✓ built in 127ms
```

### Decisions made

- Extended `rowKey` on both `PrizeTable` call sites from `row.team` to
  `` `${row.sport}-${row.team}` ``. The brief didn't mention this explicitly,
  but leaving it as `row.team` would reintroduce a visible bug the fix is
  meant to kill: React would warn on duplicate keys and could misrender
  the HOU-NFL/HOU-NCAAF rows once both exist in the same table.
- Added `sport` to the tuple assertions in
  `test_most_trusted_teams_rank_by_pick_rate` (line ~399) even though that
  test only pins a tuple (not a full dict) and therefore wasn't failing —
  the brief called out that line as one to check, and the fixture already
  has NFL/NCAAF teams, so verifying the full `(team, sport, pick_rate,
  cover_rate)` tuple there costs nothing and closes the loop.

## Change 2 — remove the pick-history section

### What was edited

- `frontend/src/pages/Player.tsx`
  - Module docstring (top of file): rewrote the sentence claiming the stats
    "and the pick history are computed together server-side and must
    agree" — it no longer describes anything that exists.
  - Removed `import PickHistory from "../components/PickHistory";`.
  - Removed the `<section>` with `<h2>Pick history</h2>` and the
    `<PickHistory history={history} />` call.
  - Changed `const { stats, history } = current.detail;` to
    `const { stats } = current.detail;` (the destructured `history` was
    otherwise unused after the section's removal).
- `frontend/src/components/PickHistory.tsx` — deleted outright.
- `frontend/src/api.ts` — kept `PickHistoryRow` and `PlayerDetail.history`
  unchanged in shape; added a one-line doc comment on `history` stating the
  SPA no longer renders it but the ai-server `pickem-analysis` skill reads
  it via `GET /api/players/{id}`.
- `frontend/src/theme.css` — removed `table.board td .spread`,
  `table.board tr.group-row th`, `.res`, `.res--correct`, `.res--incorrect`,
  `.res--missing` (all PickHistory-exclusive, confirmed dead by grep below).
  Kept `table.board td.muted` / `.muted` (shared with `ChartPrompt.tsx` and
  `WeekReview.tsx`) and `.group-note` (shared with `Compare.tsx`). Renamed
  the section comment from `/* pick history */` to
  `/* shared table bits */` since nothing exclusive to pick-history remains
  in that block.
- `app/api.py` / `_pick_history` — **untouched**, as instructed; confirmed
  via `git diff --stat app/api.py` showing no output on this branch.

### Greps proving nothing dangles

```
$ grep -rn "PickHistory" frontend/src
frontend/src/api.ts:175:export interface PickHistoryRow {
frontend/src/api.ts:193:  history: PickHistoryRow[];
```
(Only the intentionally-kept type and field remain; the component and its
import/usage are gone.)

```
$ grep -rn '"res"\|res--correct\|res--incorrect\|res--missing\|res--pending\|group-row' frontend/src
(no output)
```
(Confirms the removed CSS selectors have zero remaining references.)

Pre-removal grep that justified deleting the component in the first place:
```
$ grep -rn PickHistory frontend/src
<showed only Player.tsx importing/using it, plus the component's own
internals and api.ts's type — no other consumer>
```

### Gate: lint + build (no backend change, so pytest run only to confirm no regression)

```
$ npm run lint        # exit 0, same 4 pre-existing warnings as above
$ npm run build       # ✓ 617 modules transformed (down from 618 before deletion)
                       # dist/assets/Player-*.js 8.86 kB (down from 11.45 kB pre-removal)
$ .venv/bin/pytest -q # 546 passed, 7 deselected, 2 warnings in 6.85s
```

### Decisions made

- Kept `PickHistoryRow`/`PlayerDetail.history` exports exactly as the brief
  required (never deleted, even though now unused by the SPA) — oxlint
  raised no "unused export" complaint in this run, but the comment makes
  the reason durable for the next person who looks.
- `.group-note` and `.muted` were left in `theme.css` despite living in the
  "pick history" comment block, because each is actively used elsewhere
  (`Compare.tsx`'s `group-note`, `ChartPrompt.tsx`/`WeekReview.tsx`'s
  `muted`) — removing them would have broken those pages' styling.

## Final verification (both commits applied)

```
$ .venv/bin/pytest -q
546 passed, 7 deselected, 2 warnings in 6.79s

$ cd frontend && npm run lint   # exit 0, pre-existing warnings only
$ npm run build                 # ✓ 617 modules transformed, built in 127ms
```

## Files touched (absolute paths)

- `/Users/alfredbot.ai.butler/Documents/repos/pickem/app/scoring/stats.py`
- `/Users/alfredbot.ai.butler/Documents/repos/pickem/tests/test_stats.py`
- `/Users/alfredbot.ai.butler/Documents/repos/pickem/frontend/src/api.ts`
- `/Users/alfredbot.ai.butler/Documents/repos/pickem/frontend/src/pages/Player.tsx`
- `/Users/alfredbot.ai.butler/Documents/repos/pickem/frontend/src/pages/Analytics.tsx`
- `/Users/alfredbot.ai.butler/Documents/repos/pickem/frontend/src/components/PickHistory.tsx` (deleted)
- `/Users/alfredbot.ai.butler/Documents/repos/pickem/frontend/src/theme.css`
- `/Users/alfredbot.ai.butler/Documents/repos/pickem/.context/CHANGELOG.md`

No subagents were dispatched and no reviewer was invoked, per instructions.
Branch `fix/team-sport-collision` was not pushed or merged — that step was
not requested.
