# pickem-chart glossary — the semantic contract

The same definitions `stats.py` uses. The checker grades against this table:
a deviation from it, without a caveat explaining why, is a FAIL.

| League word | SQL |
|---|---|
| correct / hit / won | `p.result = 'CORRECT'` |
| wrong / lost | `p.result = 'INCORRECT'` |
| graded | `p.result IN ('CORRECT','INCORRECT')` |
| missed | `p.result = 'MISSING'` |
| still pending | `p.result = 'PENDING'` |
| underdog / dog | `p.pick_spread > 0` (0 and NULL are neither — excluded, as the site does) |
| favorite / chalk | `p.pick_spread < 0` |
| home / away pick | `p.picked_team = 'HOME'` / `'AWAY'` |
| team picked | `CASE p.picked_team WHEN 'HOME' THEN g.home_team ELSE g.away_team END` |
| week | `weeks.id` (**not** `nfl_week`; the pool's period order) — label it "Week N" |
| completed week | `weeks.status = 'final'` |
| NFL / college | `g.sport = 'NFL'` / `'NCAAF'` |
| Monday night | `g.is_monday_night = 1` |
| divisional game | `th.conference = ta.conference AND th.division = ta.division` with `JOIN teams th ON th.abbr = g.home_team JOIN teams ta ON ta.abbr = g.away_team` (NFL only; NCAAF has no rows) |
| the crowd / consensus | majority side among *graded* picks on the game: `(SELECT CASE WHEN SUM(picked_team='HOME') > SUM(picked_team='AWAY') THEN 'HOME' WHEN SUM(picked_team='AWAY') > SUM(picked_team='HOME') THEN 'AWAY' END FROM picks q WHERE q.game_id = g.id AND q.result IN ('CORRECT','INCORRECT'))` — a 50/50 game has no crowd |
| favorite covered / upset | winner vs line: an upset is `g.pool_spread < 0 AND g.away_score > g.home_score` or `g.pool_spread > 0 AND g.home_score > g.away_score`, only when `g.status = 'final'` |
| tiebreaker guess / error | `tiebreaker_answers.value` vs the Monday-night total; only meaningful on final weeks |
| me / my / I | `p.player_id = :player_id` — always |

Things the schema cannot answer (say so): weather, injuries, odds other
than the pool line, money lines, other sites' lines, anyone's picks before
kickoff, prize money (that is the engine's job — point them to the
leaderboards).
