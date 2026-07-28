---
name: restore
description: Restore from a backup tarball. DESTRUCTIVE -- overwrites current DB state.
model: claude-sonnet-4-6
effort: medium
permission_mode: default
required_tools: [Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion]
max_turns: 30
tags: [operations, destructive]
---

# Restore

You restore the ai-server's database and audit logs from a backup tarball.
This is a **destructive** operation -- it overwrites the current database state.
Use extreme caution and always confirm with the user before proceeding.

## CRITICAL: run this as a `god`/terminal session, NOT a normal queued job

Restore must **stop the runner, web, and bot** before touching the database.
You are running inside the runner — if a normally-queued `/task restore …` job
tries to stop the runner, it SIGTERMs **its own session** mid-restore (exit 143),
leaving services down and the DB half-swapped. Therefore:

- Restore is an **operator procedure**: run it from a terminal on the Mac Mini,
  or via a `god` break-glass session that can survive the runner going down.
- If you were dispatched as an ordinary job and detect you are the live runner's
  child, STOP and report: "Restore cannot run as a queued job (it would kill the
  runner mid-restore). Run it from a terminal or a god session." Do not proceed.

## Inputs you will receive

Extract from the job description (and optionally `payload`):
- **tarball_path** (required): path to the backup `.tar.gz` file
- **date** (optional): the date label of the backup (used in confirmation prompt)

## Locating a backup

Backups live in two places (see `scripts/backup.sh`):

- **Local:** `volumes/backups/backup-<date>.tar.gz` — the primary source.
- **Off-site:** Cloudflare R2 bucket `ai-server-backups/` — the disaster copy, used
  when the local disk is gone or the local tarball is missing/corrupt.

If the requested tarball isn't present locally, pull it from R2 first (requires
`rclone` + the `r2:` remote configured):

```bash
rclone lsl r2:ai-server-backups/                      # list available off-site backups
rclone copy r2:ai-server-backups/backup-<date>.tar.gz volumes/backups/
```

Then use the local path as `tarball_path` below.

## Procedure

1. **First confirmation.** Use `AskUserQuestion` to confirm the restore:
   "You are about to restore from a backup. This will OVERWRITE the current
   database. Type EXACTLY 'RESTORE <date>' to proceed (where <date> is the
   backup date, e.g. RESTORE 2026-04-15)."

   Parse the response. If it does not match `RESTORE <date>` exactly (case
   sensitive), abort with: "Restore cancelled -- confirmation did not match."

2. **Check backup age.** If the backup is more than 30 days old (based on the
   date in the filename or tarball metadata), require a **second confirmation**:
   "This backup is more than 30 days old (<date>). Restoring it will lose all
   data since then. Type EXACTLY 'CONFIRM OLD RESTORE' to proceed."
   If the second confirmation doesn't match, abort.

3. **Verify the tarball.** Check that the tarball exists and test its integrity:
   ```bash
   test -f "<tarball_path>" && tar tzf "<tarball_path>" > /dev/null 2>&1
   ```
   If either check fails, abort with: "Tarball not found or corrupted: <path>"

4. **Stop services.** Production is launchd-supervised — `run.sh stop` is a
   no-op there (no `volumes/pids/`), and `KeepAlive` would relaunch anything you
   kill. Bootout the launchd agents so they stay down:
   ```bash
   UID_N=$(id -u)
   for svc in runner web bot; do
     launchctl bootout "gui/$UID_N/com.assistant.$svc" 2>/dev/null || true
   done
   sleep 3
   # Verify nothing is still bound to the DB:
   pgrep -fl "src.runner.main|src.gateway" || echo "services down"
   ```
   If services are NOT down after this, abort: "Services did not stop cleanly.
   Aborting restore -- manual intervention needed." (They are restarted with
   `launchctl bootstrap gui/$UID_N ~/Library/LaunchAgents/com.assistant.<svc>.plist`
   in step 9.)

5. **Extract to temp.** Create a temporary directory and extract the tarball:
   ```bash
   RESTORE_TMP=$(mktemp -d)
   tar xzf "<tarball_path>" -C "$RESTORE_TMP"
   ```

6. **Restore database.** The database is named **`assistant`** (confirm with
   `grep POSTGRES_DSN .env` — it is `.../5432/assistant`). Look for a `pg_dump`
   file in the extracted contents (typically `*.sql` or `*.dump`) and restore it:
   ```bash
   dropdb --if-exists assistant
   createdb assistant
   psql assistant < "$RESTORE_TMP/<dump_file>"
   ```
   If the dump is in custom format (`.dump`), use `pg_restore -d assistant` instead
   of `psql`. NEVER use `aiserver` — that is a phantom name; loading into it would
   silently leave the real `assistant` DB untouched.

7. **Restore audit logs.** If the tarball contains an `audit_log/` directory,
   additively merge it into `volumes/audit_log/`:
   ```bash
   rsync -a "$RESTORE_TMP/audit_log/" volumes/audit_log/
   ```
   This is **additive** -- it does not delete existing audit log files that
   aren't in the backup. Audit logs are append-only by design.

8. **Clean up temp directory.**
   ```bash
   rm -rf "$RESTORE_TMP"
   ```

9. **Restart services.**
   ```bash
   UID_N=$(id -u)
   for svc in runner web bot; do
     launchctl bootstrap "gui/$UID_N" "$HOME/Library/LaunchAgents/com.assistant.$svc.plist" 2>/dev/null || \
       launchctl kickstart -k "gui/$UID_N/com.assistant.$svc"
   done
   sleep 5
   curl -so /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:8080/health   # expect 200
   ```
   Verify `/health` returns 200 and the runner heartbeat is fresh.

10. **Report.** Provide a summary:
    - Backup date restored from
    - Number of jobs in restored database (if queryable)
    - Date range of audit logs restored
    - Any anomalies (missing dump file, partial extraction, etc.)
    - Reminder: project repos are NOT part of backups (they're separate git repos)

## Hard rules

- **Never restore without confirmation.** The RESTORE <date> confirmation is
  mandatory and must match exactly. No exceptions.
- **Never delete backups during restore.** The tarball is read-only during
  this process. Never remove, move, or modify backup files.
- **Second confirmation for old backups.** Any backup older than 30 days
  requires a second explicit confirmation.
- **Project repos are not in backups.** Project directories under `projects/`
  are separate git repos and are NOT included in the database backup tarball.
  Make this clear in the final report.
- **Audit log restore is additive.** Never delete existing audit log files
  during restore. The rsync uses `-a` (archive) without `--delete`.
- **permission_mode is default** (not acceptEdits). This skill requires
  explicit user approval for destructive operations because permission_mode
  does not auto-approve edits.

## Gotchas (living section -- append when you learn something)

- **Project repos aren't in backups**: the user may expect them to be. Always
  remind them in the final report.
- **Database name is `assistant`** (from `POSTGRES_DSN`), NOT `aiserver`. A
  restore into `aiserver` is a silent no-op that reports success while the real
  DB is untouched — the single worst failure mode of this skill. Always confirm
  with `grep POSTGRES_DSN .env` before dropping/creating.
- **Restore stops the runner** — never run it as an ordinary queued job (it
  kills its own session). Terminal or `god` session only.
- **Custom format dumps**: `.dump` files need `pg_restore`, not `psql`. Check
  the file extension before choosing the restore command.
- **Partial tarballs**: if the tarball was created during an active write, it
  may be incomplete. The `tar tzf` integrity check catches most of these, but
  not all. If the dump file is truncated, `psql` will error partway through --
  the database will be in a broken state. The user will need to re-restore
  from a different backup.
- **Services must be stopped**: restoring while services are running will
  cause connection errors and potential data corruption. Always stop first.

## Files this skill updates as part of write-back

- Database state (destructive overwrite)
- `volumes/audit_log/` (additive merge from backup)
- No file-level CHANGELOG update -- this is an operational action, not a code change
