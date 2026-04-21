# Gotchas

> **What this file is for**: Non-obvious traps, unexpected behaviors, and things that look like they should work but don't.
>
> **When to add an entry here**: When a session hit a trap — something implicit, an ordering requirement, a race condition, an environment-specific behavior — that a future session should know about before making similar changes.
>
> Append entries newest-first. Each entry should include a date header,
> the symptom or pattern, the fix or approach, and (when possible) a
> reference to the audit log that led to the finding.
>
> This file is seeded empty. Claude sessions working in this module should
> append here when they learn something reusable (see `.context/PROTOCOL.md`).

<!-- Append entries below this marker. Do not delete the marker. -->
<!-- APPEND_ENTRIES_BELOW -->

## 2026-04-20 — healthcheck launchd silently ran with `checked=0`

**Symptom**: `volumes/logs/healthcheck.out.log` showed `checked=0 healthy=0 failed=0` on every 5-min tick despite manifests being present. `last_healthy_at` stopped updating, so the landing page status dots for `type: service` projects went stale (and would have gone gray for apps with a nonexistent dot rule).

**Root cause**: launchd runs scripts with a minimal PATH — `/opt/homebrew/bin` is NOT included. `yq` lives there, so the manifest read (`yq '.slug' "$manifest"`) silently returned empty strings, and the loop body skipped every project as "no port configured". `volumes/logs/healthcheck.err.log` contained `yq: command not found` on every tick but the `.out.log` summary line hid the problem.

**Fix**: Prepend Homebrew paths at the top of `scripts/healthcheck-all.sh`:
```bash
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
```
Alternatively, put `EnvironmentVariables` in the launchd plist — but exporting inside the script keeps the fix local and doesn't require re-bootstrapping launchd.

**Related**: Same trap hit projects' own launchd scripts (see "Project launchd can't find Python modules" below). Any launchd-invoked script that shells out to brew-installed tools needs to set PATH.

## 2026-04-20 — Unmatched `*.chrispiserchia.com` subdomains return empty 200 from Caddy

**Symptom**: User typed `www.chrispiserchia.com` (or any subdomain without a Caddy site block) and got a blank page. HTTP 200, size 0.

**Root cause**: The cloudflared tunnel ingress rule is `*.chrispiserchia.com` → `localhost:80` (wildcard), so any subdomain reaches Caddy. Caddy with no matching site block for a hostname just returns an empty 200 response — not a 404, not an error. This is easy to miss because curl reports success.

**Fix**: Add explicit site blocks for every subdomain you want to behave sensibly. For `www.` the simplest is a redirect to apex:
```caddy
http://www.chrispiserchia.com {
    redir https://chrispiserchia.com{uri} permanent
}
```
**Prevention**: When debugging "blank page" issues on the domain, always test with `--resolve $host:80:127.0.0.1 http://$host/` to see whether the empty body is a Caddy miss or an upstream issue. Empty body = no matching Caddy host.

## 2026-04-20 — cloudflared TLS internal error connecting to Caddy

**Symptom**: Tunnel shows "tls: internal error" even with `noTLSVerify: true`.

**Root cause**: Caddy's `tls internal` generates self-signed certs. The error is server-side (Caddy rejecting the handshake), not client-side.

**Fix**: Use HTTP between cloudflared and Caddy. The tunnel itself is encrypted end-to-end; localhost hop doesn't need TLS. All Caddy site blocks use `http://` prefix.

## 2026-04-20 — cloudflared system service config location

**Symptom**: cloudflared service starts but tunnel has no active connections.

**Root cause**: System service (root) looks at `/etc/cloudflared/config.yml`, not `~/.cloudflared/`. Credentials file must also be at `/etc/cloudflared/`.

**Fix**: `sudo cp ~/.cloudflared/config.yml /etc/cloudflared/` and copy the `<tunnel-uuid>.json` file.

## 2026-04-20 — cloudflared plist missing `tunnel run` arguments

**Symptom**: Service starts but does nothing — default plist just runs `cloudflared` with no subcommand.

**Fix**: Add `tunnel` and `run` args to the plist ProgramArguments. Use `sudo launchctl bootstrap system` (not old `launchctl load`).

## 2026-04-20 — Project launchd can't find Python modules

**Symptom**: `ModuleNotFoundError` in project error logs. Works from terminal but not from launchd.

**Root cause**: launchd runs with minimal PATH. pyenv shims not in PATH.

**Fix**: Set `PYENV_ROOT` and pyenv shims in plist EnvironmentVariables, or use full path to pyenv python in `start_command`.

## 2026-04-20 — macOS TCC gates ~/Documents/

**Symptom**: "permission denied" on file read/write inside `~/Documents/`.

**Root cause**: macOS Transparency/Consent/Control gates `~/Documents/`, `~/Desktop/`, `~/Downloads/` behind Full Disk Access.

**Fix**: Server must live in `~/Library/Application Support/ai-server`, not `~/Documents/`.
