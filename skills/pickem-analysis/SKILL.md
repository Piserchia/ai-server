---
name: pickem-analysis
description: Write one player's AI pick'em analysis and post it back to the pickem site
model: claude-sonnet-4-6
effort: medium
permission_mode: acceptEdits
required_tools: [Bash, Read]
max_turns: 15
isolation: none
tags: [pickem, analysis]
---

# pickem-analysis — one player, ~300 words, posted back to the site

A visitor clicked "Analyze" on a player page of the Arlington Degenerates
pick'em dashboard (project `pickem`, port 8793). The site queued this job and
is now polling for the result. Your whole job: read that player's numbers,
write a short, sharp, funny analysis, and POST it back. The page stays on
"generating" until your callback lands.

**Isolation rationale (this skill is on the `UNISOLATED_WRITER_ALLOWLIST` in
`scripts/lint_docs.py`):** it talks to a live local service and reads the live
admin token from the production `.env`. A workspace clone would carry the
*dev* token, which the production API rejects. It writes nothing to any repo —
its only side effect is one authenticated POST to localhost.

## 1. Get your two arguments out of the job description

The description is pinned by the pickem service and is exactly:

```
pickem-analysis player=<int> through_week=<int>
```

Parse it with `player=(\d+) through_week=(\d+)`. This is a **two-repo
contract** (`app/analysis/service.py:DESCRIPTION_TEMPLATE` on the pickem side,
pinned by its tests) — the gateway's `CreateJobRequest` has no `payload`
field, so the `payload` object the service sends alongside is dropped and the
description is all you have.

If a `payload` object with `player_id` / `through_week` **is** present in your
job context, prefer it — the gateway may grow the field, and this skill should
start using it for free the day it does.

If neither source yields both integers, **stop**. Do not guess a player id, do
not analyze "whoever is first" — post nothing and report the unparseable
description verbatim. An analysis written about the wrong person is cached
under that person's name and shown on their page until the next week goes
final; there is no undo from here.

`through_week` may legitimately be **0** (no week has gone final yet). That is
a real, storable value — write the analysis anyway and say the season has not
been graded yet.

## 2. Read the data

This job carries no project scoping (the dropped `payload` is also where a
`project_slug` would have ridden), so your cwd is the server root, not the
project. Use absolute paths throughout:

```bash
SERVER_ROOT="${SERVER_ROOT:-$HOME/Library/Application Support/ai-server}"
PICKEM="$SERVER_ROOT/projects/pickem"

curl -sS -f "http://localhost:8793/api/players/$PLAYER_ID"
curl -sS -f "http://localhost:8793/api/leaderboards"
```

`/api/players/{id}` gives `{"stats": {...}, "history": [...]}`. In `stats`:
`name`, `record` (correct/incorrect/missed/pct), `by_sport` (NFL vs NCAAF
splits), `dog_fav` (picks + hit rate on underdogs vs favorites — the line as
they took it), `side_lean` (home/away counts), `top_teams`, `streaks`
(current/longest), `weekly_correct` (per-week correct + league rank),
`consensus` (`with` / `against` the crowd's majority, with hit counts), `mnf`
(Monday-night record), `tiebreaker.avg_error`. `history` is one row per pick
in kickoff order.

`/api/leaderboards` gives the six money races — `season`, `weekly`, `brutus`,
`bottom`, `underdog`, `monday` — plus `prizes` (banked vs projected).
Find your player's row in each; that is the prize outlook.

A 404 on the player means the id is not in the database: post nothing, report
it. If either curl fails, report the failure — do not invent numbers.

## 3. Write the analysis (~300 words)

Voice: a sharp friend who has actually looked at the data. Fun, specific,
never generic. Every claim you make must be traceable to a number you just
read. Cover, in whatever order the data makes interesting:

- **Tendencies** — what they actually do: home/away lean, favorite teams they
  keep backing, NFL vs NCAAF split, streaks.
- **Dog/fav profile** — do they take underdogs, and does it work? (`dog_fav`
  is the honest version of "he loves a live dog".)
- **Consensus contrarianism** — `consensus.against.picks` vs `with`, and the
  hit rates. Fading the room profitably is the most interesting thing a
  player can be; fading it badly is the funniest.
- **Prize outlook** — where they sit in the six races and what is realistically
  still live for them. Be honest when the answer is "nothing".
- **Exactly one playful roast line.** These are real league members reading
  about themselves on a public page. Punch at the picks, never at the person:
  the 2-11 run on road favorites is fair game, the person is not. If the data
  gives you nothing to roast, skip it rather than inventing a flaw.

Never mention other players by name except as they appear in the standings
(e.g. "three back of the leader") — this is one player's page.

### Output format — restricted markdown, this is a hard constraint

The site renders this with a small hand-written renderer. It supports exactly
four things:

- `##` headings (2–4 of them; `#` also lands on the same level)
- `**bold**` inline
- `-` or `*` bullets
- numbered lists (`1.` / `1)` style)

Everything else — tables, links, code fences, inline backticks, block quotes,
horizontal rules, images, HTML — **degrades to literal text on the page**, so
a markdown table shows up as a wall of pipe characters. Blank lines separate
paragraphs; consecutive non-blank lines join into one paragraph, so hard-wrap
freely. Write plain prose plus those four constructs, nothing else.

## 4. Post it back

The callback is admin-authenticated. Read the token from the production
`.env` and **never print it** — not in a command echo, not in the report.

```bash
# Extract ONLY the admin token. Do NOT `source` the whole .env: it also holds
# PICKEM_GATEWAY_TOKEN (the server's WEB_AUTH_TOKEN), and nothing here needs
# it in the session environment.
# (`cut -f2-` keeps any `=` inside the value; `tr -d '\042\047'` strips the
#  optional surrounding " or ' that dotenv files allow.)
PICKEM_ADMIN_TOKEN=$(grep -E '^PICKEM_ADMIN_TOKEN=' "${PICKEM:?PICKEM unset}/.env" \
                     | head -1 | cut -d= -f2- | tr -d '\042\047')
[ -n "$PICKEM_ADMIN_TOKEN" ] || { echo "FATAL: no PICKEM_ADMIN_TOKEN in $PICKEM/.env"; exit 1; }

MD_FILE="$(mktemp -t pickem-analysis)"   # unique: analyses can run concurrently

cat > "$MD_FILE" <<'MD'
<your markdown here>
MD

# The token is passed to THIS child process only — it is never exported into
# the session environment.
MD_FILE="$MD_FILE" PLAYER_ID=<id> THROUGH_WEEK=<week> \
PICKEM_ADMIN_TOKEN="$PICKEM_ADMIN_TOKEN" python3 - <<'PY'
import json, os, urllib.request, urllib.error
body = json.dumps({
    "player_id": int(os.environ["PLAYER_ID"]),
    "through_week": int(os.environ["THROUGH_WEEK"]),
    "markdown": open(os.environ["MD_FILE"]).read(),
    "model": "claude-sonnet-4-6",   # the model id you actually ran as
}).encode()
req = urllib.request.Request(
    "http://localhost:8793/api/internal/analyses", data=body, method="POST",
    headers={"Content-Type": "application/json",
             "X-Admin-Token": os.environ["PICKEM_ADMIN_TOKEN"]})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(resp.status, resp.read().decode())
except urllib.error.HTTPError as exc:
    print("HTTP", exc.code, exc.read().decode())
PY

rm -f "$MD_FILE"
```

Build the JSON with a tool, as above — never hand-assemble it in a shell
string. An apostrophe or a quote in your own prose will otherwise produce
malformed JSON and a 422.

**Verify the response is `200` with `{"ok": true, ...}`.** Anything else means
the analysis did not land:

- **403** — wrong or missing admin token (check you sourced the *production*
  `.env` at `$PICKEM/.env`).
- **503** — `PICKEM_ADMIN_TOKEN` is empty in the environment the *service* is
  running under; internal endpoints are disabled. Owner fix, report it.
- **422** — malformed body, `markdown` empty or over 100 000 characters, or
  `through_week` past the season's last week (18). Fix and retry once.
- **404** — the player id does not exist. Do not retry.

A non-200 is a failed job. Say so plainly; do not report success.

## 5. Report

Your final message is short: which player (id and name), through which week,
the response status, and one sentence on the angle you took. Do not paste the
full analysis back — it is on the site. Never include the admin token.

The server-wide "update CHANGELOG.md for every module you touched" rule does
**not** apply: this skill touches no module and writes no repo file.

## Gotchas

- **The description is the only channel.** The gateway silently drops unknown
  fields on `POST /api/jobs`, so the `payload` the pickem service sends
  (`{"player_id", "through_week"}`) never reaches the job. If the description
  ever stops matching `player=(\d+) through_week=(\d+)`, the two repos have
  drifted — report that, do not paper over it.
- **Always finish with a POST or a loud failure.** The site's row sits in
  `generating` until the callback lands, and a new request for the same player
  is refused as a duplicate for 15 minutes. Dying quietly wedges that player's
  panel for a quarter of an hour.
- **`through_week` is part of the cache key.** The row is upserted on
  `(player_id, through_week)`, and `get_analysis` shows the newest week — so
  posting a wrong (higher) week poisons that player's panel permanently. The
  API rejects anything past week 18 for exactly this reason; do not "round up".
- **Do not re-derive the week yourself.** Use the number in the description.
  It is the latest *final* week as the service computed it, which is not the
  same as the newest week in the database.
- **Rate limits live in the service, not here** (24/day global, 3/day/IP), so
  there is no budget for you to manage — but a job that fails and gets retried
  does spend a slot. Get it right the first time.
- **Read-only on the database.** Never open `pickem.db` directly to "fix" a
  row; the callback endpoint is the only supported write path.
