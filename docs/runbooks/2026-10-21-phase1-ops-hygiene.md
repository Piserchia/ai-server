# Observability Phase 1 — ops-hygiene owner runbook (2026-10-21)

Plan: `docs/superpowers/plans/2026-10-21-observability-phase1-recut.md` (task
C1; §7 owner actions; §8 measurements to record). Spec:
`docs/superpowers/specs/2026-10-05-observability-and-trading-unblock-design.md`
§9 (Phase-1 row), §12 **D4** (account confirmations) and **D5** (ops debt).
Origin: the P0 plan's runbook (`2026-09-25-multi-model-platform-p0.md` Task 13
Step 6), re-cut against the prod facts the 2026-10-21 scout found:
`pmset autorestart 0`; rclone 1.74.3 installed with **zero remotes** (100
nightly `offsite SKIP`, 0 OK — no off-site copy of anything exists); the
`atlas` DB is **5.9 GB** and was dumped nowhere; the root disk is 228 GB with
75 GB free; 10 of 14 `com.assistant.*` plists failed `plutil -p` (raw `&&`).

These steps need `sudo`, account credentials, money or a human judgement
call, so no job runs them. Do them in order; each has a verification line.
Everything runs in the **production checkout**
(`cd ~/Library/Application\ Support/ai-server`) unless a step says otherwise.
Never invoke `pipenv` inside anything launchd executes; by hand it is fine.

## 0. Entry probes (2 min, read-only)

    curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/api/jobs      # → 401 (WEB_AUTH_TOKEN is set)
    plutil -p ~/Library/LaunchAgents/com.assistant.*.plist | grep -c CLAUDE_CODE_OAUTH_TOKEN   # → 0 after §5's reinstall
    plutil -p ~/Library/LaunchAgents/com.assistant.*.plist > /dev/null          # → no "invalid" lines after §5

Before §5 the third line prints parse errors for the plists written with a
raw `&&` — that is the finding C1 fixes, not a new problem. The first probe
must read `401` (a `200` means the dashboard is unauthenticated — stop and
set `WEB_AUTH_TOKEN` in prod `.env`, an owner-only file).

## 1. Auto-restart after power loss (sudo, 1 min)

    sudo pmset -a autorestart 1
    pmset -g | grep autorestart          # → autorestart 1   (was 0 on 2026-10-21)

## 2. Off-site backups to Cloudflare R2 (account credentials, ~25 min)

`scripts/backup.sh` already uploads when an `r2:` rclone remote exists; with
zero remotes it has logged `offsite SKIP` every night. One-time:

1. Cloudflare dashboard → R2 → create bucket `ai-server-backups`; create an
   R2 API token (Object Read & Write, this bucket only). Note the account
   id, access key id and secret access key — they go into rclone's config
   only, never into the repo or `.env`.
2. `rclone config` → new remote named exactly **`r2`**, storage `s3`,
   provider `Cloudflare`, the three values above, endpoint
   `https://<account-id>.r2.cloudflarestorage.com`.
3. Verify: `rclone lsd r2:` lists `ai-server-backups`.
4. Run one backup now and read the log:

       bash scripts/backup.sh && tail -8 volumes/logs/backup.log

   expected lines: `atlas dump OK (<size>) …`, `seal SKIP` (until §3),
   `offsite OK r2:ai-server-backups/backup-<date>.tar.gz`,
   `offsite prune OK (>60d)`, `backup … (<size>)`.
5. **Card on file.** R2 is free only **≤ 10 GB-month** and only on an
   account with a payment method on file (spec §12a row 4). Add the card,
   then confirm the bucket stays inside the allowance:
   `rclone size r2:ai-server-backups`. `backup.sh` prunes tarballs older
   than 60 days on both sides (`rclone delete --min-age 60d` off-site,
   `find -mtime +60` locally) and the weekly atlas dump at 35 days off-site
   (`--min-age 35d`), 7 days locally (`-mtime +7`). The atlas dump goes up on
   **Sundays only** (D-P1-6); re-size after the first measurement in §8 —
   if the `-Fc` dump is larger than ~1.5 GB, five weekly copies plus 60
   tarballs will not fit the free tier and the owner picks: shorter atlas
   retention, or accept the metered overage.

## 3. Seal key for the encrypted secrets bundle (5 min)

`backup.sh` now writes `secrets.tar.enc` into every tarball (the server
`.env`, the atlas **canonical** `.env` at `~/Documents/repos/atlas/.env` —
the file `provision_env_files` copies from — and
`~/.cloudflared/{config.yml,cert.pem,<tunnel>.json}`), AES-256-CBC with
PBKDF2 (200 000 iterations) — **only when this key exists**. The key must
live outside every backup AND in the password manager, or the bundle is
useless after a disk loss.

    mkdir -p ~/.config/ai-server
    openssl rand -base64 48 > ~/.config/ai-server/backup-seal.key
    chmod 600 ~/.config/ai-server/backup-seal.key
    cat ~/.config/ai-server/backup-seal.key     # paste into the password manager as "ai-server backup seal key"
    bash scripts/backup.sh && grep 'sealed secrets' volumes/logs/backup.log | tail -1
    # → `sealed secrets OK (env, atlas.env, cloudflared)`; a `WARN sealed secrets PARTIAL (missing: …)` line
    #   names what this host is missing — fix ATLAS_ENV / ~/.cloudflared before relying on the bundle

`BACKUP_SEAL_KEY=<path>` overrides the location for both `backup.sh` and
the drill. `backup.sh` never copies `~/.config/ai-server/` anywhere.

## 4. Restore drill (the Phase-1 exit criterion; 5 min for the assistant leg — the atlas leg takes about as long as a full `pg_restore` of the 5.9 GB dump and needs ~2× its uncompressed size free in the cluster's data directory, so tens of minutes on this host is normal, not a hang)

    bash scripts/restore-drill.sh
    # expected after §2 + §3:
    #   PASS assistant restore: <n> jobs
    #   PASS atlas restore: <schema.table> <rows> rows
    #   PASS sealed secrets: <k> entries
    #   PASS off-site copy present
    #   PASS

Before §2/§3 the first run on this host reads `PASS` on both DB legs with
two WARNs (`WARN sealed bundle present but no seal key` / `WARN no sealed
secrets in this backup`, and `WARN off-site: rclone r2: remote not
configured`) — exit 0. A `FAIL` line names the leg; fix and re-run. The
drill restores into the throwaway databases `restore_drill_assistant` /
`restore_drill_atlas` and drops them on exit; it never touches `assistant`
or `atlas`. One `restore-drill … result=PASS|FAIL` line lands in
`volumes/logs/backup.log`. Record the date of the first PASS and the atlas
`-Fc` size (`grep 'atlas dump OK' volumes/logs/backup.log | tail -1`) in the
plan's §8 — that measurement sizes D-P1-6.

## 5. Timer install on prod (5 min; the full install outside market hours)

Right after the C1 deploy, re-render the timers only — no service restart:

    bash scripts/install-launchd.sh timers-only
    # `timers-only` is what pins VENV_PY in the four timer plists. Until then the scripts
    # resolve the venv by `.project` match under ~/.local/share/virtualenvs (on a host with
    # both checkouts the old first-match glob selected the DEV venv — schedule-monitor did so
    # from 2026-10-05 until the 2026-10-22 whole-tier review fix).
    launchctl list | grep com.assistant                       # backup, healthcheck-all, schedule-monitor, cost-reconcile, sync-learnings
    plutil -p ~/Library/LaunchAgents/com.assistant.backup.plist | grep -c VENV_PY   # → 1

Then, once after C1 and again after E7, the **full** install — it restarts
runner/web/bot, so pick a quiet moment (outside market hours; nothing
queued):

    bash scripts/install-launchd.sh
    plutil -p ~/Library/LaunchAgents/com.assistant.*.plist > /dev/null      # every plist parses now
    plutil -p ~/Library/LaunchAgents/com.assistant.*.plist | grep -c CLAUDE_CODE_OAUTH_TOKEN   # → 0

The service plists keep the `&&` fix from the next full install; until
then they run as before (launchd tolerated the raw `&&`; only `plutil`
refused it).

## 6. Ollama: delete the three stale weights (10 min; spec D5 = yes)

Nothing in `src/` calls Ollama today; these three are six months old and
were never used. Delete them unless you override (say so in the plan's §8):

    ollama list                                   # phi3:mini, deepseek-coder-v2:16b, mistral — ~14 GB
    ollama rm phi3:mini deepseek-coder-v2:16b mistral
    df -h /                                       # ≈ 14 GB freed

The pulls (`qwen3.5:4b`, `embeddinggemma`), `OLLAMA_MAX_LOADED_MODELS=1`
and the keep-alive setting are **Phase 4** (spec §9 row 4, in-process
utility) and are deliberately not done here — pulling weights nothing
calls is the mistake being cleaned up.

## 7. D4 confirmations (12 min; auth config, never by a job)

Record each with the date in `.context/modules/runner/skills/GOTCHAS.md`
— that note **is** the record (the spec dropped the `attestation` approval
kind because nothing in scope writes one).

- **Max tier**: confirm 5x / 20x on claude.ai.
- **No metered spend**: claude.ai → Billing: usage credits $0, auto-reload
  OFF, monthly spend limit $0 (`overflow_credits: disabled` — the only
  metered Anthropic path is usage credits; the weekly `cost-reconcile` DM
  on 5-minute cache writes is the tripwire).
- **Privacy**: claude.ai → Settings → Privacy → "Help improve Claude" OFF
  (30-day retention instead of 5 years).
- **Devin**: its bundled `claude` must be the unmodified binary signed in
  on your own `/login` (`claude /status` → "Login method: Claude account");
  no third-party harness signs in with the Max credential.
- `claude setup-token` is **not** a Phase-1 step: no Phase-1 code reads a
  token from the environment, so minting a one-year credential only widens
  exposure. Nothing puts a token into a plist, `.env` or a shell profile —
  §0's `plutil` grep is the check.

## 8. Retire bingo's PostToolUse hook — through the bingo repo (10 min)

`projects/baseball-bingo/.claude/settings.json` carries a `hooks` block (a
PostToolUse `check-context-writeback.sh`) and is tracked in the **bingo**
repo. E1's settings-override refusal therefore *observes* it instead of
refusing it: bingo jobs keep running with an audited
`settings_override_observed` event and one ops DM a day. That is a stated,
bounded exception with an owner exit, and this is the exit.

It is a **project** change and never an INV-4 server patch: do it in the
bingo repo's own delivery path.

1. Move the hook out of `.claude/settings.json` — into the project's own
   tooling (a Makefile/script target the skill calls) or delete it if the
   writeback check is obsolete.
2. Commit and deploy through bingo's own path; the server pulls nothing.
3. Confirm the exception is gone:

       grep -c hooks projects/baseball-bingo/.claude/settings.json          # → 0

Until it is gone, expect the observe arm, not a refusal, for bingo.

## 9. What to write back

| Measurement | Where |
|---|---|
| atlas `-Fc` dump size, nightly tarball size (first `atlas dump OK` line) | plan §8 table, row "atlas `-Fc` dump size" |
| first `offsite OK` + `offsite prune OK` lines | plan §8, row "first off-site `rclone copy`" |
| first restore-drill PASS date | plan §8 ("the restore drill passes") + hosting GOTCHAS |
| `WEB_AUTH_TOKEN` probe → 401; `plutil` credential grep → 0 | plan §8, last row |
| D4 confirmations (§7) with dates | `.context/modules/runner/skills/GOTCHAS.md` |
| Ollama override, if any | plan §8 |
