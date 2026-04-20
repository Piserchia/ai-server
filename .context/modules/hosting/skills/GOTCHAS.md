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
