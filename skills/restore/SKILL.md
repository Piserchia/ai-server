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

## Inputs you will receive

Extract from the job description (and optionally `payload`):
- **tarball_path** (required): path to the backup `.tar.gz` file
- **date** (optional): the date label of the backup (used in confirmation prompt)

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

4. **Stop services.** Shut down the runner, web gateway, and bot:
   ```bash
   bash scripts/run.sh stop
   ```
   Verify processes have stopped. If they haven't after 10s, abort with:
   "Services did not stop cleanly. Aborting restore -- manual intervention needed."

5. **Extract to temp.** Create a temporary directory and extract the tarball:
   ```bash
   RESTORE_TMP=$(mktemp -d)
   tar xzf "<tarball_path>" -C "$RESTORE_TMP"
   ```

6. **Restore database.** Look for a `pg_dump` file in the extracted contents
   (typically `*.sql` or `*.dump`). Restore it:
   ```bash
   dropdb --if-exists aiserver
   createdb aiserver
   psql aiserver < "$RESTORE_TMP/<dump_file>"
   ```
   If the dump is in custom format (`.dump`), use `pg_restore` instead of `psql`.

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
   bash scripts/run.sh start
   ```
   Wait a few seconds and verify processes are running.

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
- **Database name**: the database is called `aiserver`. If this changes, update
  the dropdb/createdb commands.
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
