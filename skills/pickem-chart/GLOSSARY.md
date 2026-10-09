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
| favorite covered / upset | **never** derive cover from `home_score`/`away_score` — the site reads it off graded picks, not the final score. Favourite side = `CASE WHEN g.pool_spread < 0 THEN 'HOME' WHEN g.pool_spread > 0 THEN 'AWAY' END` (0/NULL = no favourite, exclude). The side that covered = `CASE WHEN p.result='CORRECT' THEN p.picked_team WHEN p.result='INCORRECT' THEN (CASE p.picked_team WHEN 'HOME' THEN 'AWAY' ELSE 'HOME' END) END` for any graded pick on the game (every graded pick on a game agrees). "Favourite covered" = that side equals the favourite side; "upset" = it does not. (`app/scoring/stats.py` `_graded_by_game`, feeding `favorite_cover_pct`.) |
| tiebreaker guess / error | the tiebreaker game is the game with the LOWEST non-null `g.tiebreaker_order` in the week (**not** "the Monday-night game"); it only counts when `w.status = 'final'`, that game's `g.status = 'final'`, and its total is not 0-0. Error = `ABS(t.value - (g.home_score + g.away_score))` with `tiebreaker_answers t ON t.player_id = p.player_id AND t.week_id = w.id`. (`app/scoring/engine.py` `tb_actual_map`.) |
| me / my / I | `p.player_id = :player_id` — always |

Things the schema cannot answer (say so): weather, injuries, odds other
than the pool line, money lines, other sites' lines, anyone's picks before
kickoff, prize money (that is the engine's job — point them to the
leaderboards).
