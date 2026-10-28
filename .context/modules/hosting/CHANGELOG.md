# Changelog: hosting

## 2026-10-22 — backup.sh: the atlas probe names the maintenance database

**Agent task**: Observability Phase 1 post-deploy verification (plan `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §8, C1 accept).
**Files changed**:
- `scripts/backup.sh` — the atlas existence probe is `psql -d postgres -tAc …`; the whole-tier review's M11 rewrite (`psql -tAc …`, no database) connected to a database named after the OS user, which does not exist here, so the first nightly run (2026-10-22 04:00 local) logged `atlas dump SKIP (no atlas database)` while atlas is 5.9 GB. `tests/test_scripts_syntax.py` pins the `-d postgres` form.

**Why**: the probe must behave identically under launchd (no PGDATABASE) and in a shell.

**Side effects**: none beyond the dump now running nightly; the first atlas `-Fc` size is recorded in the plan's §8 after the next run.

## 2026-10-21 — C1: `backup.sh` atlas dump + sealed secrets + 60-d retention, `restore-drill.sh`, installer timer env block + `timers-only` + plist escaping, the Phase-1 ops-hygiene runbook

**Agent task**: Observability Phase 1 re-cut plan C1 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 13 "13a" Steps 3/4/6 + Task 12 Step 5's installer piece, adapted by symbol with the C1 Deltas and D-P1-6).
**Files changed**:
- `scripts/backup.sh` — header rewritten for a 228 GB disk (the "2TB SSD, no retention cap" comments are gone); `LOG`/`ATLAS_DUMP` variables; step 1 dumps `atlas` with `pg_dump -Fc` to `volumes/backups/atlas-<date>.dump` **outside** the tarball when `psql -lqt` lists the DB (`atlas dump OK (<size>) <path>` / `WARN atlas dump failed` + the partial file removed / `atlas dump SKIP (no atlas database)`); step 4b seals `.env`, the atlas canonical `.env` (`ATLAS_ENV`, default `~/Documents/repos/atlas/.env`) and `~/.cloudflared/{config.yml,cert.pem,*.json}` into `secrets.tar.enc` with `openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass file:"$SEAL_KEY"` (`BACKUP_SEAL_KEY` → `~/.config/ai-server/backup-seal.key`; `seal SKIP (no key at …)` when absent; `WARN sealing failed (bundle omitted)` on error); the rclone block uploads the tarball nightly then prunes `--min-age 60d --include 'backup-*.tar.gz'`, and on Sundays (`date -u +%u` = 7) uploads the day's atlas dump and prunes `--min-age 35d --include 'atlas-*'`; step 7 is the local retention: `backup-*.tar.gz -mtime +60`, `atlas-*.dump -mtime +7`. Every new step is `if …; then … else log; fi` or `|| true` under `set -euo pipefail`; no `pipenv` anywhere; the plain `.env` is copied only into the seal staging dir, never into `$TMP`.
- `scripts/restore-drill.sh` (new, executable) — owner-run on prod: newest tarball (or argv[1]) → `restore_drill_assistant` via `psql < db.sql` (`PASS assistant restore: <n> jobs`; FAIL on restore error or 0 rows), newest `atlas-*.dump` → `restore_drill_atlas` via `pg_restore --no-owner --no-privileges` (`PASS atlas restore: <schema.table> <rows> rows`; a non-zero `pg_restore` with tables present still passes — it exits 1 on any warning; WARN when no dump exists), `secrets.tar.enc` unsealed with the same openssl parameters and `tar -tf` entry NAMES counted (`PASS sealed secrets: <k> entries`; WARN when no bundle or no key; FAIL when a present key cannot unseal or `secrets/env` is missing), off-site `rclone lsf` (informational WARN). `dropdb --if-exists` both throwaways in the EXIT trap; verdict line + `restore-drill <tarball> result=PASS|FAIL` appended to `volumes/logs/backup.log`; exit 0/1. `set -uo pipefail` (no `-e`: every leg reports). PATH is **appended** with the Homebrew dirs, not prepended, so the operator's shell and the tests' fake pg tools win.
- `scripts/install-launchd.sh` — `timers-only` argv mode (`TIMERS_ONLY=1` wraps the services loop in `if (( ! TIMERS_ONLY )); then … fi`; the sync-learnings and `install_timer` timers always re-render); `install_timer` gains `EnvironmentVariables` (`PATH` = `${VENV_DIR}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin`, `VENV_PY=${VENV_DIR}/bin/python`, `DISABLE_ERROR_REPORTING=1`, `DISABLE_TELEMETRY=1`); every `ProgramArguments` string in the three heredocs writes `&amp;&amp;` instead of a raw `&&` (plist = XML; launchd decodes it — verified by rendering a timer plist with a fake `launchctl` and `plutil -lint` → OK, `plutil -p` shows `cd "…" && bash scripts/backup.sh`); usage/header comments + the closing "Controls" list (`plutil -p`, `timers-only`).
- `docs/runbooks/2026-10-21-phase1-ops-hygiene.md` (new) — §0 entry probes (`curl … /api/jobs` → `401`; `plutil … grep -c CLAUDE_CODE_OAUTH_TOKEN` → `0`; every plist parses after §5), §1 `sudo pmset -a autorestart 1`, §2 R2 bucket + token + `rclone config` remote `r2` + card-on-file + the free-tier sizing rule, §3 seal key, §4 restore drill + first-run expectations, §5 `install-launchd.sh timers-only` then the full install outside market hours, §6 Ollama prune of the three stale weights (spec D5; pulls/keep-alive are Phase 4), §7 D4 confirmations, §8 bingo's PostToolUse hook via the bingo repo, §9 the measurements to write back to the plan's §8.
- `tests/test_scripts_syntax.py` — `test_backup_dumps_atlas_and_seals_secrets`, `test_backup_has_retention_rule` (`-mtime +60`, `--min-age 60d`, `-mtime +7`, `--min-age 35d --include 'atlas-*'`), `test_restore_drill_exists_and_parses`, `TestRestoreDrill` (5: the script copied into a fixture tree and run end to end with fake `createdb`/`dropdb`/`psql`/`pg_restore`/`rclone` on PATH that log their argv and answer the three queries, a fixture tarball, a fixture dump and a REAL openssl-sealed bundle: full PASS with both throwaways dropped and the log line; the first-run shape = PASS + two WARNs; missing dump/bundle = WARNs; 0 jobs = FAIL rc 1; no tarball = FAIL rc 1; a sealed value never appears in the output), `test_installer_timer_plists_carry_venv_env`, `test_installer_escapes_ampersands` (every heredoc body: no raw `&&`, `&amp;&amp;` present, and it parses as XML once `${…}`/`$N` are replaced), `test_runbook_exists` (the §0–§8 needles).
- `.context/modules/hosting/CONTEXT.md` (Paths + the `backup.sh`, `restore-drill.sh`, `install-launchd.sh` bullets), `.context/SYSTEM.md` (`backup.sh` row updated, `restore-drill.sh` row added), `.context/INDEX.md` + `docs/README.md` (runbook rows; the re-cut plan rows say C1 landed), `docs/TROUBLESHOOTING.md` (symptom: `offsite SKIP` / `seal SKIP` / drill `WARN`).

**Why**: spec §9's Phase-1 row and D5 — the atlas DB (5.9 GB) was dumped nowhere, no off-site copy of anything exists (100 nightly `offsite SKIP`), the secrets had no sealed copy, the bucket would have grown forever, and every timer script that calls python was dead under launchd for want of `VENV_PY`. D-P1-6 sizes the atlas dump for a 228 GB disk and R2's ≤ 10 GB-month free tier: `-Fc`, outside the tarball, 7 d local / weekly off-site / 35 d R2.

**Side effects**: one new file per night in `volumes/backups/` (`atlas-<date>.dump`, up to 8 on disk) and a few more `backup.log` lines; the nightly tarball grows by the sealed bundle only once the owner creates the key (runbook §3). Nothing changes on prod until the deploy + `bash scripts/install-launchd.sh timers-only` (plan §7 row 5). The drill creates and drops two throwaway databases on the prod cluster when the owner runs it — never run from dev (its `volumes/backups` is empty and the dev `.env` points at prod).

**Gotchas discovered**: (1) a launchd plist is XML — a raw `&&` in a `<string>` loads under launchd (it is lenient) but fails `plutil -p`/`-lint`, so a "10 of 14 plists invalid" finding is cosmetic for running services and real for anyone validating them; `&amp;&amp;` is decoded before bash sees it. (2) `pg_restore` exits non-zero on ANY warning (a missing extension, an owner role that does not exist), so a drill that keys only on its exit code reports a usable restore as FAIL — count tables after the restore instead. (3) A script that prepends the Homebrew dirs to PATH cannot be driven with fake tools; `restore-drill.sh` appends them. (4) `rclone delete r2:… --min-age 60d` without `--include` would also sweep the atlas dumps (harmless at 35 d, but the two rules should not overlap).

## 2026-10-21 — B4: `scripts/cost-reconcile.py` + the weekly `com.assistant.cost-reconcile` timer

**Agent task**: Observability Phase 1 re-cut plan B4 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 16 "16b"/"16c", adapted by symbol with the three B4 Deltas).
**Files changed**:
- `scripts/cost-reconcile.py` (new, executable) — the spec §2.8 calibration anchor from the JSONL ledger: `--windows 30,7` (default; `--days N` alias) → one `pricing.render_table` block per window (per-model, `unpriced` with the provider named, the per-kind step, approximated lanes, medians) + `render_sdk_reconcile` per window + `render_weekly_allowance` once (the quota window is not a report window); `--db` runs `DB_SQL` (`SUM(cost_usd_list)`, `SUM(sdk_cost_usd)` per `COALESCE(model_served, resolved_model)` — the JSONL leg's precedence — over `status='completed'` rows in each window) through `pricing.render_db_delta`; `--seed-lane-budgets [PATH]` writes `write_lane_seed` from the SHORTEST window (default `<server_root>/volumes/telemetry/lane_budget_seed.json`) and prints the same values as a table; `--json` emits ONE document (`audit_dir, until, windows[], weekly_allowance, credit_signature, prices_as_of` + `db[]` / `lane_seed` when asked). Exit 0 report / 1 `credit_signature` (reserved) / 2 no audit dir / 3 the run itself failed (the `--db` leg is wrapped: `DB leg failed: <ExcType>: <msg>` + traceback on stderr → rc 3; `__main__` catches any other exception the same way, `cost-reconcile failed: …` → rc 3 — review round 1). `INDEX.jsonl` is skipped; sub-directories (D1's `schedules/`) are not globbed. `main(argv, *, db_rows=)` takes the DB leg as an injectable callable and `src.db` / `sqlalchemy` are imported only inside it, so neither the hand run nor the tests open Postgres without `--db`.
- `scripts/cost-reconcile-run.sh` (new, executable) — the launchd wrapper: `cd "$PROJECT_DIR"` BEFORE the interpreter resolution (`VENV_PY` export → `pipenv --venv` → `~/.local/share/virtualenvs/<basename>-*`; `import src.config` guard; an unusable/absent interpreter is a `FATAL` log line + an owner DM + exit 0), then `"$VENV_PY" scripts/cost-reconcile.py --windows 30,7 --db --seed-lane-budgets >> volumes/logs/cost-reconcile.log`; `send_alert()` (notify send `--kind ops_alert --severity warn` from the project root, raw-curl fallback reading the two `.env` names, always returns 0) fires on rc=1 with the credits-signature text (rc=1 is the CLI's reserved code, so this branch is the billing DM only) and on any other non-zero rc with "weekly run failed (rc=N; 3 = the run itself failed …)". Never `pipenv run`.
- `scripts/install-launchd.sh` — `install_timer "cost-reconcile" "scripts/cost-reconcile-run.sh"` with `StartCalendarInterval Weekday 1 / Hour 7 / Minute 30` (Monday 07:30 local), through the existing 3-arg helper; nothing else changed.
- `tests/test_scripts_syntax.py` — `TIMER_SCRIPTS` += `scripts/cost-reconcile-run.sh` (the installer cross-check and the `pipenv run` ban now cover it), `ALERTER_SCRIPTS` += the wrapper (notify before curl); `test_cost_reconcile_timer_installed` (the exact interval block), `test_cost_reconcile_wrapper_runs_the_cli_with_both_windows_the_db_leg_and_the_seed` (argv, log path, cd-before-`VENV_PY=`, `FATAL`, executable bits), `TestCostReconcileAlert` (the function driven with a fake interpreter: the pinned notify argv + cwd, and the no-creds fallback path is a WARN line with rc 0).
- `tests/test_pricing.py` — `TestCli` (14): the CLI loaded by `importlib` over a fixture ledger (three jobs across the two windows, a Codex job, a `seven_day` reading, an `INDEX.jsonl` that must not count): both blocks + the per-kind step, the `--json` shape, `--days` / `--windows` order, exit 1 on a 5-m write (text and JSON), exit 2, an empty dir is a report, the seed file + table (shortest window, `1.2`, approximated lanes, the exact `atlas` figure) and its default path under `settings.server_root`, the `--db` leg with injected rows (two calls with 30-d / 7-d spans, both cost columns, family labels) in text and JSON, "no `--db` → the callable is never invoked", the `DB_SQL` pins, an AST check that no top-level import names `src.db` / `sqlalchemy`, and (review round 1) `test_db_leg_failure_is_not_the_credit_signature` — an injected raising `db_rows` → rc 3, the `DB leg failed:` stderr line, no credits-signature text/JSON.
- `.context/modules/hosting/CONTEXT.md` (Paths + the timer bullet), `.context/SYSTEM.md` (two script rows after `codex-canary.sh`; the pricing row's `(B4)` marker dropped), `.context/modules/db/CONTEXT.md` (`jobs.cli_version` vs `executor_started.cli_version`), `.context/modules/runner/CONTEXT.md` (the pricing bullet names its consumer), `.context/INDEX.md` + `docs/README.md` (the re-cut plan rows now say B1–B4 landed; an INDEX row for the reconcile), `docs/TROUBLESHOOTING.md` (two symptoms: `unrecognized_model: silent empty success`; the cost-reconcile DM / rc=1 vs rc=3).

**Review round 1 applied (2026-10-21)**: (major) rc=1 was also Python's default exit for an uncaught exception, so a Postgres outage in the `--db` leg would have DM'd the owner "check claude.ai billing" — the DB leg and `__main__` now exit 3 with a `… failed: <ExcType>: <msg>` stderr line (asyncpg/SQLAlchemy messages carry no DSN or password); the wrapper's generic branch and the TROUBLESHOOTING "Root cause" name rc=3; `test_cost_reconcile_wrapper_…` pins `if (( rc == 1 ))` + the rc=3 text. (minor) `TestCli::test_default_windows_…` dropped its vacuous `or out.count("SDK") >= 2` alternative. (minor) the runner/db docs-only B4 entries gained `**Gotchas discovered**: none.`

**Review round 2 applied (2026-10-21)**: (major) `main` calls `db_rows` once PER WINDOW and `_db_rows` wraps each call in its own `asyncio.run`, while `src.db.engine` is a module-level pooled `AsyncEngine` — the 30-d leg's pooled asyncpg connection (bound to the first, now-closed loop) would be handed back inside the 7-d leg's loop and the pre-ping would raise "attached to a different loop" (not a DBAPI error, so the pool re-raises instead of recycling): rc=3 and the "weekly run failed" DM every Monday, and Delta 3's 7-d DB leg never measured. Inherited from the P0 design of record (Task 16's per-window `asyncio.run`), not introduced. Fix: `_db_rows_async` imports `engine` beside `async_session` and runs the session block under `try: … finally: await engine.dispose()`, so every `asyncio.run` ends with the pool emptied in the loop that created it (one fresh connection per window; `db_rows(since, until)` stays injectable and the two-call pin stands). Source-level pin `TestCli::test_db_leg_disposes_the_engine_per_run` (AST: the `async with` is inside a `try` whose `finally` awaits `engine.dispose()`); a live check remains the §8 first prod run (Delta 2). (minor) the CLI docstring and the TROUBLESHOOTING hand re-run say why the bare `--seed-lane-budgets` is omitted from dev: it resolves under `settings.server_root` = production's `volumes/`; pass an explicit PATH or omit the flag. (minor, same fix) the real DB leg now has a textual pin — the injected-rows tests never execute `_db_rows` / `_db_rows_async`.

**Why**: spec §9's Phase-1 row requires the reconcile to print BOTH windows and the per-kind step every week and to re-seed the lane budgets (round-2 #18: the 30-d mean predates the alpha flywheel), and its exit criterion — `cost_usd_list` and `sdk_cost_usd` agree within 1 %, or the divergence is recorded with the rate the CLI uses — is MEASURED by this script's first prod run (Delta 3; recorded in plan §8, never "fixed" by editing `pricing.py`). D-P1-8: a launchd timer, not a schedule row, so it needs no model, no quota and no runner.

**Side effects**: one new log (`volumes/logs/cost-reconcile.log`), one new artefact (`volumes/telemetry/lane_budget_seed.json`, rewritten weekly; nothing reads it in Phase 1), one new timer on the next `install-launchd.sh` run on prod (plan §7 — not installed by a job), and at most one owner DM per week (rc ≠ 0 only). The `--db` leg is read-only SQL. Until 008 + B3 are deployed the DB leg prints `DB: none` rows — expected (Delta 2).

**Gotchas discovered**: (1) `lane_for` puts EVERY owner-channel job (telegram/web/pwa/cli) in the `owner` lane before looking at the skill, so an atlas-* skill launched from Telegram seeds `owner`, not `atlas`; the fixture's atlas job is scheduler-born for that reason. (2) `argparse`'s `nargs="?"` + `const=""` is what makes `--seed-lane-budgets` work both bare (default path) and with a PATH; a following flag (`--json`) is not swallowed because it starts with `-`. (3) A substring check "no `src.db` above `main(`" is wrong for a lazy import inside a helper — pin top-level imports with `ast` instead. (4) A module-level pooled `AsyncEngine` (`src.db.engine`) must not be reused across `asyncio.run` loops: a pooled asyncpg connection is bound to the loop that opened it, and the next loop's pre-ping raises a non-DBAPI `RuntimeError` the pool does not recycle. Every other `asyncio.run` caller in the repo runs once per process; a script that runs it N times must `await engine.dispose()` at the end of each (or use one loop for all N).

## 2026-10-21 — A7: out-of-band alerters prefer `python -m src.notify send`, curl kept as the fallback; `tests/test_scripts_syntax.py` is born

**Agent task**: Observability Phase 1 re-cut plan A7 (`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` §6; design of record P0 plan Task 13 "13b" + the Task 12 `test_scripts_syntax.py` preamble).
**Files changed**:
- `scripts/healthcheck-all.sh` — interpreter resolution after `LOG=`: `VENV_PY="${VENV_PY:-}"` (the timer plist's export, when one exists) → `(cd "$PROJECT_DIR" && pipenv --venv)` → pipenv's deterministic `~/.local/share/virtualenvs/<basename>-*` → none, guarded by `(cd "$PROJECT_DIR" && "$VENV_PY" -c 'import src.config')` (both probes in a cd-first subshell: this script never cd's and the editable install is inert under `~/Documents`); an unusable or absent interpreter is a WARN line and the curl path. New `notify_send(kind, text)` = `"$VENV_PY" -m src.notify send --kind <kind> --severity critical --text <text>` from the project root, returning 1 when there is no interpreter or the CLI did not deliver. The runner-down and swing-watchdog alert sites become `if notify_send ops_alert "$msg"; then … elif curl …; then … (curl fallback)`; the `.env` reads and the creds-missing guards stay for the fallback.
- `scripts/schedule-monitor.sh` — the existing venv block now honours an exported `VENV_PY` first (same §4 order as healthcheck); `send_dm` tries `"$VENV_PY" -m src.notify send --kind ops_alert --severity warn` and falls back to the unchanged curl; new `count_schedule_deferred()` counts `"kind": "schedule_deferred"` records with `ts` inside the last 24 h under `volumes/audit_log/schedules/*.jsonl` (D1's stream; 0 when the directory does not exist yet), logs `schedule_deferred_24h=<n>`, appends a `FINDING deferred: …` line to the findings (so the 12 h-rate-limited DM fires) and `deferred_24h=<n>` to the Sunday summary. The header comment no longer quotes the literal `pipenv run` phrase (the new test greps for it).
- `tests/test_scripts_syntax.py` (new, 30 collected) — `bash -n` over every `scripts/*.sh`; `TIMER_SCRIPTS = (backup, healthcheck-all, schedule-monitor)` with the `pipenv run` ban and the installer cross-check (`install_timer "<x>" "scripts/<y>"` calls in `install-launchd.sh` must all be listed, so the list cannot drift); the alerter order pins; and fixture-driven runs of `notify_send()` (fake interpreter records argv + cwd; rc 0/1 paths) and `count_schedule_deferred()` (sub-directory only, 24 h window, other kinds ignored).
- `.context/modules/hosting/CONTEXT.md` — Paths + the two alerter bullets.

**Why**: the alert-history row (spec §3) must exist for out-of-band alerts too, but the out-of-band doctrine (healthcheck-all header, 2026-07-30 and 08-17 incidents) forbids depending on the bot, the runner or Postgres for delivery: `python -m src.notify send` sends over direct HTTP and only then records the row, exits 1 whenever the DM was not delivered, and the raw curl stays behind it. `pipenv run` never appears in a timer script (the 2026-09-14..10-05 rc=127 incident); `codex-canary.sh` is hand-run and excluded.

**Side effects**: none on the probes — every new line is inside the guarded alert paths or before them with `|| true` semantics. `healthcheck.log` gains one `WARN … alerts fall back to curl` line per run on a host with no resolvable venv (none expected on prod: `schedule-monitor` resolves the same way daily). B4 and E10 append their timer scripts to `TIMER_SCRIPTS` in the commit that creates them; D1 is the producer of the records `count_schedule_deferred` reads.

**Gotchas discovered**: `pipenv --venv` must run from the project root (it finds the Pipfile by cwd) — healthcheck-all never cd's, hence the subshell. A bash function extracted by name and sourced into a throwaway shell is a cheap way to test a script's alert path with a fake interpreter without running the probes.

## 2026-10-05 — schedule-monitor.sh: resolve venv Python directly (watchdog unbroken)

**Files created**: none
**Files changed**: `scripts/schedule-monitor.sh` (replaced
`pipenv run python -m src.runner.schedule_adherence` with direct
`$VENV_PY -m ...` invocation; added `$HOME/.local/bin` to PATH; added
`pipenv --venv` resolution with a glob fallback to
`~/.local/share/virtualenvs/<basename>-*`; FATAL log + clean exit if neither
locates a venv).
**Why**: launchd's `com.assistant.schedule-monitor` timer has run daily at
07:15 UTC since 2026-09-14 under a minimal env with no `pipenv` on PATH, so
the `pipenv run python ...` call died with `pipenv: command not found` and
`rc=127` every single day — silently killing the only out-of-band
schedule-adherence watchdog. `schedule_rollup` grades runs that exist; this
monitor is what notices DARK / NEVER_RAN / STUCK / FAILURE_STREAK — the
08-17 governor-dark incident class. Mirrors `install-launchd.sh`'s own
`pipenv --venv → $VENV_DIR/bin/python` pattern so launchd never has to
locate `pipenv` itself. Evidence: ops-manager weekly review 2026-10-05;
`volumes/logs/schedule-monitor.log` showed `pipenv: command not found` on
every run from 2026-09-14 through 2026-10-04.
**Side effects**: the daily DM resumes — the owner will again see findings
DMs (rate-limited one per 12h) and the Sunday fleet summary. First
post-deploy run (next 07:15 UTC) may surface a backlog of previously-silent
findings; that is signal, not regression. Launchd `.plist` already matches
current conventions (same `install_timer` function as `backup` /
`healthcheck-all`); no plist edit required.
**Gotchas discovered**: launchd timers installed via
`install-launchd.sh:install_timer` do NOT bake the venv into
`EnvironmentVariables.PATH` the way the service plists (runner/web/bot) do
(install-launchd.sh:96-100). Shell scripts invoked by those timers must
resolve the project venv themselves — do NOT rely on `pipenv` being on PATH.
The analogous timers (`backup.sh`, `healthcheck-all.sh`) only use system
tools (brew-provided `yq`, `curl`, `psql`), so they were unaffected by the
same gap.

## 2026-09-10 — Caddy `trusted_proxies`: stop discarding visitor IPs

**Agent task**: pickem whole-branch review fix wave (T18) — finding 7.

**Files changed**:
- `Caddyfile` — added a `servers { trusted_proxies static 127.0.0.1/32
  ::1/128 }` block to the global options, with a comment pointing at the
  hosting CONTEXT.
- `.context/modules/hosting/CONTEXT.md` — new "Visitor IPs: both hops must be
  trusted" subsection under Traffic flow (with the three-row outcome table),
  plus Gotchas entries: the symptom, the live evidence, the `setup-caddy.sh`
  regeneration footgun, the per-project `--forwarded-allow-ips '127.0.0.1,::1'`
  reminder, and `::1:0` as the half-fixed state.
- pickem `manifest.yml` (separate repo, commit `7ac09d5`) —
  `--forwarded-allow-ips '127.0.0.1,::1'`.

**Why**: cloudflared runs on this Mac and dials Caddy over loopback, so every
request in the world reaches Caddy from 127.0.0.1. Caddy treats an untrusted
peer's `X-Forwarded-For` as spoofable and **replaces** it with the peer
address instead of appending — so Cloudflare's real-visitor IP was discarded
at the door and every hosted app saw 127.0.0.1 as the client. Confirmed live
in `volumes/logs/project.pickem.out.log`, where every line read
`INFO: 127.0.0.1:<port> - "GET ..."` for genuine internet traffic. The
practical damage is silent, not loud: pickem's per-IP AI-analysis rate limit
was collapsed into a single bucket shared by the entire league (and by
everyone else on the internet). pickem's manifest `start_command` already
carried `--proxy-headers --forwarded-allow-ips 127.0.0.1` for the
Caddy→uvicorn hop, but that is the *second* hop and it could not help on its
own: uvicorn was faithfully forwarding the 127.0.0.1 Caddy had already
substituted. (That app-side value turned out to need widening too — see the
next paragraph. Caddy was the blocking half, not the whole fix.)

**Second hop, found while verifying**: the Caddy fix alone moved the logged
client from `127.0.0.1:<port>` to `::1:0` — better, but still one shared
bucket for the whole internet. cloudflared's ingress targets
`http://localhost:80` and macOS resolves `localhost` to `::1` first, so
Caddy's peer is IPv6 loopback and Caddy appends `::1` to the chain; uvicorn
walks the chain from the right and stops at the first untrusted host, which
with only `127.0.0.1` allowed was `::1`. Fixed in the pickem repo
(`manifest.yml` → `--forwarded-allow-ips '127.0.0.1,::1'`, commit `7ac09d5`)
and the plist regenerated with `./scripts/register-project.sh pickem`. The
lesson is generalized in CONTEXT.md as a three-row table: all three
configurations serve traffic perfectly and only one reports the real client,
so **this must be verified by reading the project log, never by reasoning**.

**Verified end to end 2026-09-10**: `curl https://pickem.chrispiserchia.com/healthz`
over IPv6 logged `2600:4040:44af:...:fda3:0`, over IPv4 logged
`173.73.118.137:0` — both matching this Mac's egress IP as independently
reported by `cloudflare.com/cdn-cgi/trace`. A forged
`X-Forwarded-For: 203.0.113.99` sent from off-box did NOT take effect
(Cloudflare overwrites client-supplied XFF), so no spoofing hole was opened.
Apex, health and pickem all still 200 after the reload.

**Side effects**: global — applies to every vhost and every hosted project at
once, which is correct (the tunnel topology is identical for all of them).
Trust is scoped to loopback only, so nothing off-box can spoof `XFF`;
requests can only reach Caddy via cloudflared or from this Mac. Applied to
production with `caddy reload --config ./Caddyfile` (no restart, no tunnel
touch, zero downtime). **Footgun recorded**: `scripts/setup-caddy.sh`
regenerates the base `Caddyfile` from a template that does not carry this
block (nor the apex landing-page / www-redirect blocks the tracked file has
had for a while) — re-running that one-time bootstrap on a live host would
silently revert this. Noted in CONTEXT.md Gotchas; the template itself was
deliberately left alone as out of scope for this wave.

## 2026-09-03 — healthcheck-all cadence-slip false alarm (atlas 84th recurrence)

**Agent task**: self-diagnose job `4cbadd62` — atlas flagged unhealthy 20+ min.

**Runtime action**: none to atlas (project was HTTP 200 on port 8791 throughout,
external 302 = CF Access as expected, all 3 launchd services healthy).
Kickstarted `com.assistant.healthcheck-all` inline via
`launchctl kickstart -k gui/$UID/com.assistant.healthcheck-all`; cadence
resumed and all 3 projects' `last_healthy_at` refreshed to <1s.

**Files changed**:
- `docs/TROUBLESHOOTING.md` — appended 84th recurrence entry to the
  shared-cadence-slip running log (throttled to ~60-90m gaps throughout
  the day rather than a single sleep event; noted app-level UUID cast +
  FK violation noise in project.atlas.err.log is unrelated).

**Why**: canonical macOS launchd `StartInterval` throttling; the live-probe
gate and self-suppress guard fixes remain blocked by the workspace-push
meta-bug per the 51st entry, so still not re-dispatching a server-patch.

## 2026-09-01 — atlas-weekly-reports session_timeout_seconds → 3600

**Agent task**: review-and-improve — raise session_timeout_seconds to 3600
for the atlas-report-sweep schedule row so the weekly Sunday sweep stops
hitting the 1800s default.

**Files changed**:
- `scripts/seed-schedules.sh` — added payload
  `'{"session_timeout_seconds":3600}'` to the `atlas-weekly-reports` upsert
  (job_kind `atlas-report-sweep`), expanded the section comment to note the
  override and why (report-family, no `project_slug`, well below the 5400
  cap).

**Why**: the Sunday sweep does a full `atlas-dash refresh` + enumerate +
fan-out (or, when the dispatch MCP tool is unavailable, sequential
per-target reports). Under the 1800s default it was hitting the ceiling
mid-sweep; 3600s matches the cadence other governed atlas weekly rows
already carry (momo/trader/advisors/swing/value-research + value-theses).

**Side effects**: the seed script is idempotent — on the next
`server-deploy` step 3b, the `ON CONFLICT DO UPDATE` branch will overwrite
`job_payload` for the existing `atlas-weekly-reports` row with the new
payload (declared payloads win per the COALESCE rule in `upsert`). No cron
change; no other schedules touched. Cap remains at 5400 per
`SESSION_TIMEOUT_CAP_SECONDS` in `runner/main.py` — the TROUBLESHOOTING.md
guidance against reflexively bumping the timeout is for fleet-workflow
skills that should be split (e.g. momo H010); atlas-report-sweep is
already a fan-out orchestrator, so this bump gives it room to enumerate,
not to do more work inline.

**Gotchas discovered**: none — this uses the exact same
`session_timeout_seconds` payload key already carried by six other atlas
schedule rows; `resolve_session_timeout` in `runner/main.py` reads it.

## 2026-08-31 — F3/F5/F6/F7 topology fixes (EVALUATION_2026-08-30)

- `scripts/sync-learnings.sh`: allowlist narrowed — `skills/*/*.md` →
  `skills/*/{GOTCHAS,CHANGELOG,DEBUG,PATTERNS}.md`. SKILL.md is the
  runner-read machine contract; contract edits now only travel dev→prod via
  server-patch/deploy, never prod→dev via auto-publish.
- `Pipfile.lock` is now COMMITTED (was gitignored + diverged between
  checkouts — same class as the mcp 2.0.0 outage). server-deploy runs
  `pipenv sync --dev` against the tracked lock and no longer re-locks on
  prod.
- `scripts/seed-schedules.sh`: absorbed the two DB-only rows
  `atlas-daily-brief` (0 12 * * *) and `atlas-weekly-reports`
  (0 18 * * 0, kind atlas-report-sweep) so a wipe+seed keeps the
  owner-visible report cadence.
- `scripts/install-launchd.sh`: header now documents what it does NOT
  install (cloudflared system LaunchDaemon, brew postgres/redis) and the
  deliberate KeepAlive semantics (clean exit stays down).
- `.env.example`: `SERVER_ROOT` no longer hardcodes `/Users/chris` (config
  default already resolves `$HOME`); concurrency comment notes live=2 vs
  code default 4.
- Dev-tree quarantines (renames, per the no-deletion rule):
  `projects/atlas` → `projects/atlas.stale-clone-20260731.quarantined`
  (month-stale third clone), `projects/market-tracker` →
  `projects/market-tracker.retired.quarantined`. Each carries a
  QUARANTINED.md; owner may delete.

<!-- Newest entries at top. Every session that modifies this module appends here. -->

## 2026-10-22 — Whole-tier review applied: `.project`-matched venv in the three timer scripts, backup PARTIAL/trap/pg_database, drill WARNs + quoted identifier, `uninstall` removes the timers

**Agent task**: whole-tier review of `observability/phase-1` (plan `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` "Whole-tier review applied 2026-10-22").
**Files changed**:
- `scripts/healthcheck-all.sh`, `scripts/schedule-monitor.sh`, `scripts/cost-reconcile-run.sh` — the `~/.local/share/virtualenvs/<basename>-*` fallback prefers the venv whose pipenv-written `.project` equals `$PROJECT_DIR`; first-match survives only as a LOGGED fallback (`WARN no venv whose .project matches …; using first match …`). On this host both checkouts have basename `ai-server` and the first match is the DEV venv (`ai-server-SOXcmoRD` before prod's `ai-server-bpzo5SVu`) — prod's schedule-monitor had run on the dev venv since the 2026-10-05 repair, and A7/B4 had extended that to two more timers. The FATAL/WARN "searched: …" text names the `.project` rule. healthcheck-all additionally resolves LAZILY on the first `notify_send` (`resolve_venv_py()`, memoised): the 5-min tick no longer spawns the interpreter when nothing is sent, and a venv-less host no longer logs the same WARN 288 times a day.
- `scripts/backup.sh` — `sealed secrets OK (env, atlas.env, cloudflared)` only when all three sources landed, else `WARN sealed secrets PARTIAL (missing: …)` (the `cp`s are `|| true` and tar+openssl seal an empty tree — the old line said OK with nothing inside; the bundle is still written, the drill's `FAIL … lacks secrets/env` stays the stronger signal); a plain string, not an array (launchd = /bin/bash 3.2, empty arrays under `set -u`). `trap 'rm -rf "$TMP" "${SEAL_TMP:-}"' EXIT` — a killed run (ENOSPC under `set -e`, SIGTERM, launchd unload) no longer leaves `db.sql` or the plaintext `.env` copies under `$TMPDIR`. The atlas-exists probe is one `psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'atlas'"` (the `psql -lqt | … | grep -qx` pipeline under `pipefail` can report "no atlas database" on grep's early-exit SIGPIPE).
- `scripts/restore-drill.sh` — leg 3 WARNs (never FAILs: a host without the atlas dev clone or a tunnel must still pass) when the bundle lacks `secrets/atlas.env` or `secrets/cloudflared/config.yml`; the atlas row-count table is `format('%I.%I', table_schema, table_name)` so a mixed-case or reserved name is quoted instead of yielding `?` rows.
- `scripts/install-launchd.sh` — `TIMER_LABELS=(backup healthcheck-all schedule-monitor cost-reconcile)`; `uninstall` unloads and removes those plists too (they stayed loaded and kept firing against a removed checkout; the weekly cost-reconcile would have DM'd "no usable project venv python" every Monday).
- `tests/test_scripts_syntax.py` — `TestVenvResolution` (6: `.project` match beats first match / logged fallback / source pins per script, lazy+memoised healthcheck), `test_installer_uninstall_removes_every_timer`, `TestRestoreDrill::test_bundle_without_atlas_env_warns_but_passes` + `test_atlas_table_identifier_is_quoted`, backup pins (PARTIAL line, `-s` checks, EXIT trap, `pg_database` probe, no `psql -lqt`), `TestNotifySendFunction` sources `resolve_venv_py` beside `notify_send`.
- `docs/runbooks/2026-10-21-phase1-ops-hygiene.md` §3 (the OK/PARTIAL grep), §4 (the atlas leg's real duration + disk headroom), §5 (`timers-only` is what removes the dependency on the glob); `docs/TROUBLESHOOTING.md` backup symptom (PARTIAL, `pg_database`); `.context/modules/hosting/CONTEXT.md` (`pg_database`). This file: the D1 entry moved to its chronological place (it was filed between 2026-08-31 and 2026-08-18).
**Why**: review findings — one cross-checkout venv selection that was live on prod, one false-OK log line the runbook's verification greps for, one plaintext-secrets leak on a killed run, one uninstall gap, two precision points.
**Side effects**: `grep 'sealed secrets OK'` no longer matches the new OK line by itself (it carries the source list) — the runbook greps `sealed secrets`. `uninstall` now also stops the backup timer.
**Gotchas discovered**: (1) pipenv's `.project` carries a trailing newline; `$(cat …)` strips it, so the comparison is exact against `$PROJECT_DIR` (the plist's literal path — not realpath-normalised; both sides are the path pipenv was run from). (2) A `psql -lqt` pin in a test comment is still a substring: the "no `psql -lqt`" assertion forced the backup comment to say `psql -l | …`.

## 2026-10-21 — D1: the four swing supervise/trade rows declare `TRADIER_SANDBOX_TOKEN` (D-P1-7)

**Agent task**: Observability Phase 1 re-cut plan D1 (`scripts/seed-schedules.sh` slice).
**Files changed**: `scripts/seed-schedules.sh` — `atlas-swing-supervise-{edt,est}` and `atlas-swing-trade-{edt,est}` payload is now exactly `'{"project_slug":"atlas","env_required":["TRADIER_SANDBOX_TOKEN"]}'`; `atlas-swing-research` / `atlas-swing-evaluate` and the value rows are untouched; a comment block records why (declared on the row, not in the atlas manifest — atlas patches are never INV-4 server patches). `tests/test_scripts_syntax.py::test_seed_schedules_swing_rows_carry_env_required` pins the four literals and that nothing else carries a key.
**Why**: the scheduler's D1 pre-check unions `job_payload.env_required` with the manifest's; this is what makes the swing rows defer (one DM, no session) instead of running four Tradier sessions a day against a missing sandbox token.
**Side effects**: takes effect on prod only after `bash scripts/seed-schedules.sh` (the ON CONFLICT clause updates `job_payload` for declared payloads). Until the owner provisions the token in `~/Documents/repos/atlas/.env`, the four rows defer at every slot.
**Gotchas discovered**: none.

## 2026-08-18 — healthcheck-all cadence-slip false positive (baseball-bingo, 84th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended).

**Why**: self-diagnose fired for baseball-bingo unhealthy (`last_healthy_at`
36m stale at fire, stamp 07:00:48Z vs probe 07:36Z), though `/healthz`
returned HTTP 200 in 5.7ms and `/` HTTP 200 in 4.8ms on port 8790,
launchctl label `com.assistant.project.baseball-bingo` PID 3253 stable.
Atlas `last_healthy_at` was identically frozen at 07:00:49Z — canonical
shared-cadence fingerprint. `healthcheck.out.log` last successful tick
07:00:49Z (seven missed 5-min ticks: 07:05/10/15/20/25/30/35).
`com.assistant.healthcheck-all` idle between ticks (PID `-`).

**Fix**: `launchctl kickstart -k gui/$(id -u)/com.assistant.healthcheck-all`.
Cadence resumed with a tick at 07:36:58Z; both baseball-bingo and atlas
`last_healthy_at` refreshed to ~4s old. Very-low-risk auto-apply per the
self-diagnose skill.

**Still blocked**: the events.py live-probe gate that would zero these
false positives remains un-landed after 84 recurrences — workspace-push
meta-bug per TROUBLESHOOTING.md entry 51. Self-suppress guard proposed
in entries 80–83 (skip enqueue if a running/queued self-diagnose for the
same slug exists) remains the cheapest follow-up once that meta-bug
unblocks. Not re-dispatching a server-patch.

Job: `365acc34`.

## 2026-08-03 — healthcheck-all cadence-slip false positive (atlas, 61st recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended).

**Why**: self-diagnose fired for atlas unhealthy (`last_healthy_at`
20m31s stale at fire, stamp 22:03:19Z vs probe 22:23:50Z), though
`/` returned HTTP 200 in 64ms on port 8791 and all three launchd
processes (atlas / dash-scheduler / pm-edge, PIDs 24233 / 81428 /
81432) were healthy. `healthcheck.out.log` gap 22:03:19Z →
22:24:01Z = 20m42s / four missed 5-min ticks — the same
macOS-sleep-cadence-slip pattern as recurrences 43–60. No concurrent
baseball-bingo twin observed this slip.

**Fix**: `launchctl kickstart -k gui/$(id -u)/com.assistant.healthcheck-all`.
Cadence resumed with a tick at 22:24:01Z; atlas `last_healthy_at`
refreshed to <1s at 22:24:00Z. Very-low-risk auto-apply per the
self-diagnose skill.

**Still blocked**: the events.py live-probe gate that would zero
these false positives is trapped in the runtime clone by the
workspace-push meta-bug (`src/runner/workspaces.py`) — see
TROUBLESHOOTING.md entries 51–60. Not re-dispatching another
server-patch until the meta-bug is unblocked.

Job: `348ec5db`.

## 2026-08-03 — healthcheck-all cadence-slip false positive (baseball-bingo, 59th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended as
59th entry, dispatch-window twin of the atlas 58th entry immediately
above).

**Why**: self-diagnose fired for baseball-bingo unhealthy
(`last_healthy_at` 21m09s stale at fire) though `/healthz` returned 200
and `/` returned 200 on port 8790 (PID 71682, uvicorn stable for 3d16h).
`healthcheck.out.log` gap 19:19:46Z → 19:41:16Z (four missed 5-min ticks,
macOS-sleep-cadence-slip signature). The concurrent atlas twin diagnose
(job `2c663dd3`, enqueued 13ms earlier) had already kickstarted
`com.assistant.healthcheck-all` at 19:41:16Z before this baseball-bingo
job probed, so no additional kickstart was needed; a manual
`healthcheck-all.sh` run also refreshed baseball-bingo `last_healthy_at`
to <1min old. Historical anyio `TaskHandle` ImportError bursts in
`project.baseball-bingo.err.log` re-confirmed as stale (July 30 pre-restart
PID 3619); anyio 4.14.2 exports `TaskHandle` correctly at current
interpreter state. Prevention (events.py live-probe gate) still blocked
by the workspace-push meta-bug — owner action remains the unblock.

## 2026-08-03 — healthcheck-all cadence-slip false positive (baseball-bingo, 44th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended;
44+ occurrences counter bumped from 43+).

**Why**: self-diagnose fired for baseball-bingo unhealthy (`last_healthy_at`
age 21m09s at fire) though `/healthz` returned 200 in 6.1ms and `/` returned
200 in 5.4ms with full HTML on port 8790 (PID 71682 healthy).
`healthcheck.out.log` gap 13:47:17Z → 14:08:28Z (21-min slip, four missed
5-min ticks). `com.assistant.healthcheck-all` was not actively running (PID
`-`); kickstarted inline via `gui/$(id -u)/com.assistant.healthcheck-all`.
Cadence resumed 14:29:52Z, both baseball-bingo and atlas `last_healthy_at`
refreshed to 7s old (single kickstart, both projects refreshed —
shared-cadence pattern reinforced). No prevention patch landed yet;
`events.py` live-probe gate and `healthcheck-all.sh` psql-exit-status
surfacing both remain un-landed.

## 2026-08-03 — healthcheck-all cadence-slip false positive (atlas, 39th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended;
39+ occurrences counter bumped from 38+).

**Why**: `_check_project_health` in `runner/events.py` fired for atlas
(`last_healthy_at` age 35m at fire time) though the project answered
`/` HTTP 200 in 74ms on port 8791. `healthcheck.out.log` last tick
06:08:09Z — seven missed 5-min ticks in a row (06:13/18/23/28/33/38/43).
Kickstarted `gui/$(id -u)/com.assistant.healthcheck-all` inline;
cadence resumed 06:44:14Z, both atlas and baseball-bingo
`last_healthy_at` refreshed to ~2s. All three atlas launchd processes
(atlas / atlas-dash-scheduler / atlas-pm-edge, PIDs 24233/81428/81432)
were up continuously — same PID trio as recurrences 35–38, confirming
no atlas restart was needed. The prevention patch (live-probe gate in
`events.py:_check_project_health`) still un-landed — spec captured in
TROUBLESHOOTING.md and referenced in prior CHANGELOG entries.

## 2026-08-03 — healthcheck-all cadence-slip false positive (baseball-bingo, 27th recurrence)

**Files changed**: `docs/TROUBLESHOOTING.md` (recurrence note appended;
27+ occurrences counter bumped).

**Why**: `_check_project_health` in `runner/events.py` fired for
baseball-bingo (`last_healthy_at` age 21m43s) though the project answered
`/healthz` 200 in 8.5ms. `healthcheck.out.log` last tick 23:59:21Z —
four missed 5-min ticks in a row. Kickstarted
`gui/$(id -u)/com.assistant.healthcheck-all` inline; cadence resumed
00:21:19Z, `last_healthy_at` refreshed to 3s. No project restart
needed (that would be the only real downtime of the incident). The
prevention patch (live-probe gate in `events.py` `_check_project_health`)
remains unimplemented — job `f74b7415`.

## 2026-07-31 — Atlas goes GitHub-canonical; first live delivery contract (Phase E, atlas half)

**Files changed**: `.context/PROJECTS_REGISTRY.md` (atlas source + delivery
table → ACTIVE), `skills/atlas-redeploy/SKILL.md` (origin is GitHub; wording
for multi-machine commits), `docs/TROUBLESHOOTING.md` (atlas divergence
section: correct origin is now the GitHub URL). Same-day follow-up — the
every-session multi-machine procedure: root `CLAUDE.md` (push-gates dev-repo
wording), `.context/PROJECT_PROTOCOL.md` (§1.4 rebase-before-work, §4.2
delivery-branch push), `skills/app-patch/SKILL.md` (STEP 0 rebase-first);
mirrored in atlas `CLAUDE.md` §Working-on-this-repo + `docs/DEVELOPMENT.md`
(surfaces + checklist). Non-repo state changes on the
Mini (owner-directed in an interactive session): runtime clone
`projects/atlas` origin repointed local-path → `https://github.com/Piserchia/atlas.git`;
the stale dev-checkout copy `~/Documents/repos/ai-server/projects/atlas`
repointed + fast-forwarded 99 commits.

**Why**: owner decision 2026-07-31 — develop atlas from multiple machines.
GitHub `Piserchia/atlas` (master) is the source of truth; single-writer is
superseded by rebase+push single-branch integration (atlas CLAUDE.md
§Deployment topology, atlas `docs/DEVELOPMENT.md`). The atlas manifest now
carries the `delivery:` block (dev-repo topology, pull-only runtime,
gated-auto) — the first project on the 2026-07-27 segregation contract, so
runner enforcement (cwd scoping + deploy-authority gate) is live for atlas.

**Verify**: `git -C "$HOME/Library/Application Support/ai-server/projects/atlas"
remote get-url origin` → GitHub URL; `pipenv run python -c "from pathlib import
Path; from src.registry.manifest import load;
print(load(Path.home()/'Documents/repos/atlas/manifest.yml').delivery.topology)"`
→ `dev-repo`; next `/task redeploy atlas` pulls from GitHub ff-only.

## 2026-07-27 — Manifest `delivery` block documented (segregation Phase D)

**Files changed**: `.context/modules/hosting/CONTEXT.md` (manifest schema now
documents the `delivery` contract); `skills/new-project/SKILL.md` (scaffolds
dev-repo topology by default: canonical repo at `~/Documents/repos/<slug>`,
GitHub backup, pull-only `projects/<slug>` runtime clone, writes the delivery
block). No code change — the schema is parsed by `src/registry/manifest.py`
(Phase A). See `docs/superpowers/plans/2026-07-27-project-delivery-segregation.md`.

## 2026-07-12 — Commit-topology enforcement (post-incident hardening)

**Files changed**:
- `scripts/install-prod-hooks.sh` (new) — installs a pre-commit guard in the
  PRODUCTION checkout that blocks commits on main (path-gated so dev/copies
  are never affected). Bypass: `AI_SERVER_ALLOW_MAIN_COMMIT=1` (god
  break-glass; push-in-same-session mandatory per god SKILL.md).
- `scripts/sync-learnings.sh` — stray-commit safety net: unpushed commits on
  prod main are auto-published to `origin/runtime-rescue-auto` with loud
  guidance, so a stray commit can never strand work or block deploys again.
- `skills/server-deploy/SKILL.md` — step 2 re-arms the hooks every deploy
  (hooks are untracked, so this keeps them self-healing).
- `skills/god/SKILL.md` — "Committing from the host lane" section: doc
  learnings stay uncommitted; emergency code commits require immediate push.
- `CLAUDE.md` — enforcement paragraph + dev-side fetch-before-work rule.

**Why**: same-day incident — prod held one unpushed commit (`7e22db9`),
blocking the first ff-only deploy; separately dev's push was rejected because
GitHub main had moved (07-10 remediation wave). Both failure classes now have
structural enforcement, not just convention.

**How to verify**: in prod, `git commit` on main → blocked with guidance;
`bash scripts/sync-learnings.sh --dry-run` with a synthetic local commit
reports it; dev `git fetch && git merge origin/main` before push.

## 2026-07-12 — P0: sync-learnings script + launchd timer, server-deploy skill

**Files changed**:
- `scripts/sync-learnings.sh` (new) — publishes runtime doc drift (allowlist:
  `.context/**/*.md`, `skills/**/*.md`, `docs/Troubleshooting.md`) from the
  production checkout to `origin/runtime-learnings` via git plumbing
  (temp index + commit-tree) — HEAD, index, and working tree untouched, safe
  while the runner is live.
- `scripts/install-launchd.sh` — installs `com.assistant.sync-learnings`
  hourly timer (+ uninstall support).
- `skills/server-deploy/SKILL.md` (new) — the server's own deploy pipeline:
  sync learnings → stash doc drift → ff-only pull → deps/migrations →
  pytest gate → restart web/bot, runner restart detached (+20s).
- `CLAUDE.md` — Single-writer topology section (dev repo = code writer,
  production = learnings writer only).

**Why**: kill the manual "rescue runtime-written docs" workflow and give the
server the same gated deploy path atlas already had.

**How to verify**: in production: `bash scripts/sync-learnings.sh --dry-run`;
then `/task deploy server` after a dev commit.

## 2026-07-11 — Fix nightly backup: launchd PATH; stop tracking volumes/ artifacts

**Files changed**:
- `scripts/backup.sh` — Added explicit `PATH` export after `set -euo pipefail` so launchd sessions find `/opt/homebrew/opt/postgresql@15/bin/pg_dump`. Backup was silently failing with exit 127 since 2026-04 (EVALUATION_2026-07-10 §3.7).
- `.gitignore` — Replaced narrow per-file `volumes/` entries with a single `volumes/` blanket ignore. Removed `volumes/jobs.db` entry.
- `volumes/backups/backup-2026-04-17.tar.gz` — Untracked from git (was committed by accident; runtime artifact).

**Why**: Nightly pg_dump failed for ~3 months because launchd starts with `/usr/bin:/bin:/usr/sbin:/sbin` only. The old tarball sitting in git was discovered during the July eval.
**Verified**: Kicked `com.assistant.backup` after the fix; `backup-2026-07-11.tar.gz` (1.5 MB) created, `LastExitStatus=0`.

## 2026-07-10 — Next.js ISR gotcha documented

**Agent task**: Write-back for job bfcab76c — atlas skill suite refactor and new skills
**Files changed**:
- `.context/modules/hosting/skills/GOTCHAS.md` — Added entry: Next.js ISR routes need `dynamic='force-dynamic'` to avoid build-time pre-rendering failures

**Why**: A deploy (job `15bbc829`) hit a build-time pre-rendering failure on a route that depended on runtime data. Next.js pre-renders by default; adding `export const dynamic = 'force-dynamic'` forces server-side rendering per request and prevents stale/broken HTML in deployed pages.
**Side effects**: None observed
**Gotchas discovered**: Without `force-dynamic`, a build may succeed but serve stale or broken HTML at runtime.

## 2026-07-06 — External dead-man's-switch heartbeat

**Change**:
- `Caddyfile.d/health.conf` (new) — exposes only `/health` at
  `health.chrispiserchia.com` (all other paths 404), an unauthenticated public
  liveness URL for the external monitor.
- `ops/heartbeat-worker/` (new) — Cloudflare Worker with a Cron Trigger (`*/5 * * * *`)
  that polls the health URL and Telegram-DMs after 2 consecutive failures, with an
  all-clear on recovery. State in KV. Files: `wrangler.toml`, `src/index.ts`,
  `package.json`, `tsconfig.json`, `README.md`.

**Why**: Every in-process alerter (server-upkeep, done-DMs, quota) runs inside the
runner; if the runner/Mac/tunnel dies, silence looks like health. This monitor lives
off-box on Cloudflare's edge and closes that gap. Pairs with the meaningful `/health`
(gateway) + runner heartbeat (runner) landed the same day.

**Human one-time setup** (see `ops/heartbeat-worker/README.md`): route
`health.chrispiserchia.com` on the `ai-server` tunnel; `wrangler kv namespace create
HEARTBEAT_KV` and paste the id into `wrangler.toml`; `wrangler secret put
TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`; `wrangler deploy`. Reload Caddy for the new
vhost (`caddy reload --config Caddyfile`).

**How to verify**: `curl -s https://health.chrispiserchia.com/health | jq` → 200;
`launchctl stop com.assistant.runner` → 503 within ~90s and a Telegram alert after two
Worker ticks (`wrangler tail`); restart → all-clear DM.

## 2026-07-06 — Off-site backup replication to Cloudflare R2

**Change**:
- `scripts/backup.sh`: after building the local tarball, replicate it off-disk to
  Cloudflare R2 (`r2:ai-server-backups/`) via `rclone copy`. The push is guarded —
  if `rclone` isn't installed or the `r2:` remote isn't configured it logs
  `offsite SKIP`; a failed upload logs `WARN` but never fails the local backup
  (the local copy remains the source of truth). Added `backup.sh` to this module's
  Paths line (hosting now owns operational scripts).
- `skills/server-upkeep/SKILL.md`: new step 8b checks off-site backup freshness
  (`rclone lsl r2:ai-server-backups`); DMs an anomaly if the newest remote object is
  > 48h old while rclone is configured. `offsite-not-configured` is not an anomaly.
- `skills/restore/SKILL.md`: new "Locating a backup" section documents pulling a
  tarball from R2 when the local disk/copy is gone.

**Why**: Verified gap — local backups, the Postgres DB, and the append-only audit-log
institutional memory all lived on the same 2TB SSD. A single disk/hardware failure
would erase all three at once, against the mission's continuity goal. Off-site
replication + a freshness alarm closes the loop so a silently-broken upload is noticed.

**Human one-time setup required** (not automatable, no secrets in repo):
`brew install rclone`; create R2 bucket `ai-server-backups` + a scoped API token;
`rclone config` a remote named `r2` (S3-compatible R2 endpoint). Until then the push
logs `offsite SKIP` and upkeep reports `not configured` — both non-fatal.

**How to verify**:
- `bash scripts/backup.sh` writes `volumes/backups/backup-<date>.tar.gz`; with R2
  configured, `rclone lsl r2:ai-server-backups/` lists it and `backup.log` shows
  `offsite OK`. With the remote removed, the local backup still succeeds and
  `backup.log` shows `offsite SKIP`/`WARN`.
- Running `server-upkeep` with no recent remote object flags a stale-backup anomaly.

**Side effects**: None on local backup behavior (fully backward-compatible). Adds a
soft dependency on `rclone` (brew) for the off-site leg only.

**Change**:
- `projects/baseball-bingo/manifest.yml` edited from `type: static`/`web_root: web-legacy` to `type: service` with `port: 8790`, `healthcheck: /healthz`, and a `start_command` that sources a project-local `.env` for `SESSION_SECRET` before launching `uvicorn web.main:app` via the ai-server virtualenv.
- Ran `bash scripts/register-project.sh baseball-bingo`. This regenerated `Caddyfile.d/baseball-bingo.conf` from `root * web-legacy` / `file_server` to `reverse_proxy localhost:8790`, generated `~/Library/LaunchAgents/com.assistant.project.baseball-bingo.plist`, loaded it with launchd (KeepAlive on crash, RunAtLoad), reloaded Caddy, and upserted the projects row with `type=service`, `port=8790`.

**Why**: Phase 3 of the Baseball Bingo migration plan. Phase 1 (2026-04-20) built the FastAPI backend; Phase 2 (2026-04-21) added groups/shared-cards/marks + SPA; Phase 3 flips the public URL from the legacy static HTML to the live FastAPI service.

**How to verify**:
- `launchctl list | grep baseball-bingo` shows a running PID.
- `curl -sL https://bingo.chrispiserchia.com/healthz` → `{"status":"ok"}`.
- `curl -sL https://bingo.chrispiserchia.com/` returns the SPA shell.
- `curl -sI https://bingo.chrispiserchia.com/static/app.js` → `HTTP/2 200 content-type: text/javascript`.
- End-to-end POST/GET API smoke against `bingo.chrispiserchia.com/api/session` → `api/groups` succeeded with a seeded 25-cell card payload.

**Side effects**:
- `web-legacy/` remains in the project for reference but is no longer served. The reverse_proxy catches all traffic.
- `SESSION_SECRET` is stored in `projects/baseball-bingo/.env` (gitignored). Losing that file invalidates every existing session cookie; regenerate and users must re-login.
- Caddy config is now `http://` only (tunnel handles TLS); reload via `caddy reload --config Caddyfile` is idempotent.

## 2026-04-20 — Fix silent healthcheck failure + `www.` redirect

**Change**:
- `scripts/healthcheck-all.sh`: prepend `/opt/homebrew/bin` (and friends) to PATH so launchd-invoked runs can find `yq`. Previously every 5-minute tick logged `checked=0` because `yq` wasn't on launchd's bare PATH and `yq '.slug'` returned empty, causing the script to skip every manifest.
- `Caddyfile`: add a `www.chrispiserchia.com → https://chrispiserchia.com` 301 redirect. Previously `www.` (and any unmatched subdomain hitting the tunnel wildcard) fell through to a Caddy empty-200 response.

**Why**: User reported "cloudflare site appears to be broken". Investigation showed `last_healthy_at` in `projects` table hadn't been updated for 3 days (market-tracker) / ever (bingo), because the cron healthcheck wasn't actually checking anything. Separately, `www.` returned blank.

**How to verify**:
- `bash scripts/healthcheck-all.sh` reports `checked=3 healthy=3 failed=0`.
- `psql assistant -c "SELECT slug, last_healthy_at FROM projects;"` shows a fresh timestamp on `market-tracker` within the last 5 min.
- `curl -sI https://www.chrispiserchia.com/` returns `HTTP/2 301` with `location: https://chrispiserchia.com/`.
- Logs `volumes/logs/healthcheck.err.log` stop getting `yq: command not found` appended.

**Gotchas added**:
- `.context/modules/hosting/skills/GOTCHAS.md` now documents the launchd-PATH trap for shell scripts and the "blank Caddy host" trap for unmatched subdomains.

## 2026-04-18 — Seeded skills/ subdirectory per Rec 3 (§ 7 Seed module skills/ dirs)

**Change**: This module now has `.context/modules/hosting/skills/` containing stub `GOTCHAS.md`, `PATTERNS.md`, and `DEBUG.md` files. Stubs were created via `scripts/seed-module-skills.sh`; no source code modified.

**Why**: PROTOCOL.md directs sessions to append learnings to these files, but four of five modules had no skills/ directory at all, discouraging write-backs. Creating the directories with format-header stubs removes the friction and gives future sessions a template to append to. See `docs/EVALUATION_2026-04-18.md` § 7 Rec 3.

**Side effects**: None on module behavior. New lint check `check_module_skills_dirs` in `scripts/lint_docs.py` verifies these files continue to exist.


<!-- Newest entries at top. -->

## 2026-04-17 — Phase 3: Initial hosting infrastructure

**Agent task**: Build the hosting layer — Cloudflare tunnel, Caddy, project registration, healthchecks.

**Files created**:
- `scripts/setup-tunnel.sh` — One-time Cloudflare named tunnel setup (interactive)
- `scripts/setup-caddy.sh` — One-time Caddy install + Caddyfile + launchd service
- `scripts/register-project.sh` — Idempotent project registration: reads manifest.yml, generates Caddy snippet + launchd plist(s) + DB row. Supports static, service, and multi-service projects.
- `scripts/healthcheck-all.sh` — Probe all projects every 5 min, update `projects.last_healthy_at`
- `Caddyfile` (generated by setup-caddy.sh) — Base config with dashboard routing + per-project imports
- `Caddyfile.d/` (generated by register-project.sh) — Per-project Caddy snippets

**Why**: Phase 3 goal is multi-project hosting on a single public domain. The scripts automate the full lifecycle: tunnel → Caddy → register project → healthcheck.

**Design decisions**:
- Multi-service projects (market-tracker has 3 Flask servers) get separate launchd plists per sub-service and Caddy handle blocks for path-based routing. This keeps each service independently supervised and restartable.
- Manifest schema includes `mission`, `web_strategy`, and `platforms` fields so the AI server can distinguish "this IS a web app" from "this has a web shim for a native app."
- Healthchecks read from manifest files (source of truth) rather than the DB.

## 2026-08-30 — swing trading watchdog in healthcheck-all (R18)

`scripts/healthcheck-all.sh` gains `check_swing_freshness`: on market
weekdays after 16:00 UTC, if `swing.runs` (atlas DB, read via the runtime
clone's .env) shows no run inside 26h (74h Mondays), DM the owner — rate-
limited 1/12h, silent-safe pre-deploy. Out-of-band by design (the scheduler
cannot watchdog itself; spec 2026-08-27 v3 §6.2 R18). Session: trading-bots
implementation.

## 2026-09-10 (writeback: XFF gotcha correction)
- CONTEXT.md Gotchas: removed the stale "app-side --forwarded-allow-ips was
  already correct" claim (the exact half-fix misdirection the 2026-09-10
  trusted_proxies work disproved); Gotcha now states BOTH hops are required.
- skills/pickem-sync/SKILL.md: mismatch-string prose updated for the NULL-side
  sentinel shape; stale "most common cause" (pre-guard freeze) replaced with
  the open-week symptom + orphaned-PENDING escalation path.
- scripts/seed-schedules.sh: comment coupling the pickem cron to the site's
  76h stale-banner window.
