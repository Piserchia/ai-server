# pickem schema — what a chart may read

Six tables are readable in the sandbox. Nothing else exists as far as a
chart is concerned (ledgers, board, analyses and operational tables are
denied). All times are ISO-8601 UTC strings. The bound parameter
`:player_id` is always supplied and must appear in your SQL.

## players
| column | meaning |
|---|---|
| id | the player id — `:player_id` |
| name | display name |
| active | 1/0 |

## weeks  (one row per pool period; `id` IS the week number the site shows)
| id | week ordinal 1..18 — label "Week N". NOT `nfl_week`. |
| nfl_week / ncaaf_week | the leagues' own numbering (offset); do not chart these |
| status | 'open' (in progress) or 'final' (every game graded) |

## games
| id | game id |
| week_id | → weeks.id |
| sport | 'NFL' or 'NCAAF' |
| kickoff_utc | kickoff |
| home_team / away_team | CBS abbreviations: 'NE', 'LAR', 'JAC', 'WAS' … (NFL rows exist in `teams`; college abbreviations do not) |
| pool_spread | the HOME line: negative = home favored by that much; positive = away favored; 0/NULL = pick'em / no line |
| is_monday_night | 1 for the Monday-night game |
| tiebreaker_order | non-NULL on the week's tiebreaker game |
| home_score / away_score | NULL until played |
| status | 'scheduled' / 'in_progress' / 'final' — only trust scores when 'final' |

## picks  (one row per player per game; rows only exist once a game has kicked off)
| player_id, game_id | keys |
| picked_team | 'HOME' / 'AWAY' / NULL |
| pick_spread | the line AS THE PLAYER TOOK IT: > 0 took the underdog, < 0 took the favorite, 0/NULL neither |
| result | 'CORRECT' / 'INCORRECT' / 'PENDING' (game not over) / 'MISSING' (no pick submitted) |

## tiebreaker_answers
| player_id, week_id | keys |
| value | the player's guessed Monday-night total points |

## teams  (NFL only, 32 rows)
| abbr | matches games.home_team / away_team |
| name | "New England Patriots" |
| conference | 'AFC' / 'NFC' |
| division | 'East' / 'North' / 'South' / 'West' |

## Joins that are always valid
```sql
FROM picks p
JOIN games g  ON g.id = p.game_id
JOIN weeks w  ON w.id = g.week_id
LEFT JOIN teams th ON th.abbr = g.home_team
LEFT JOIN teams ta ON ta.abbr = g.away_team
WHERE p.player_id = :player_id
```

## Sandbox limits (a violation is a build failure you will see in `preview`)
one SELECT/WITH statement · no comments · ≤ 4000 chars · ≤ 8 columns, plain
identifier names (use `AS`) · ≤ 500 rows (aggregate!) · 2 s · only `:player_id`
