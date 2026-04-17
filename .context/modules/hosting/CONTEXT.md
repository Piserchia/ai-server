# Hosting module

**Paths:** `scripts/register-project.sh`, `scripts/setup-tunnel.sh`, `scripts/setup-caddy.sh`, `scripts/healthcheck-all.sh`, `Caddyfile`, `Caddyfile.d/`

## Purpose

Multi-project hosting on a single public domain via:
- Cloudflare named tunnel (stable `*.chrispiserchia.com`)
- Caddy reverse proxy with per-project snippets
- launchd plists for per-project service supervision
- 5-minute healthcheck loop

## Public interface

- `register-project.sh <slug> [--dry-run]` — add/update a project's hosting config. Reads `projects/<slug>/manifest.yml`, generates Caddy snippet + launchd plist(s) + DB row.
- `healthcheck-all.sh` — probe all projects (runs on 5-min timer via launchd)
- `setup-tunnel.sh` — one-time: create/update Cloudflare named tunnel (interactive, needs browser)
- `setup-caddy.sh` — one-time: install Caddy + base Caddyfile + launchd service

## Manifest schema

Each project declares a `manifest.yml` with:

```yaml
slug: <string>          # Unique identifier, used in DB and Caddy
name: <string>          # Human name
mission: <string>       # One-line project purpose
type: static|service|api
subdomain: <string>     # <subdomain>.chrispiserchia.com
web_root: <string>      # (static only) subdirectory to serve
web_strategy: native-web|legacy-shim|companion|planned
platforms:
  primary: ios|web|cli|api|library
  web: native|planned|not-applicable
port: <int>             # (service/api only)
healthcheck: <path>     # (service/api only)
start_command: <string> # (service/api only)
services:               # (optional) additional sub-services
  - name: <string>
    port: <int>
    start_command: <string>
    healthcheck: <path>
    path_prefix: <string>   # Caddy handle_path prefix
    api_routes: [<glob>]    # Caddy handle rules (no path stripping)
```

## Project documentation standard

Every project in `projects/` should have:
- `manifest.yml` — machine-readable hosting config (parsed by scripts)
- `.context/CONTEXT.md` — human + AI readable with standard sections:
  - **Mission**: what the project does, who it's for
  - **Platforms**: primary platform + web serving relationship
  - **Web Serving**: how it's exposed on chrispiserchia.com
  - **Architecture**: tech stack, key modules, data flow
  - **Status**: what works, what's planned
- `CLAUDE.md` — session directive pointing to `.context/`

The distinction between Mission and Web Serving prevents the hosting concern from overwriting the project's original goals.

## Dependencies

- `caddy`, `cloudflared`, `yq`, `gh` (brew-installed)
- `psql` (already there from Phase 1)

## Traffic flow

```
Internet → Cloudflare edge (TLS termination)
  → cloudflared tunnel (encrypted end-to-end)
  → Caddy localhost:80 (HTTP, no TLS)
  → per-project reverse_proxy or file_server
```

**Why HTTP on localhost**: Caddy's `tls internal` generates certs via a local CA,
but the root cert can't be installed into macOS trust store without sudo. This
causes TLS handshake failures when cloudflared connects. Since the tunnel itself
is already encrypted, the localhost hop doesn't need TLS.

## Gotchas

- `cloudflared tunnel login` needs a browser. Run at the Mac's console, not over SSH.
- `cloudflared tunnel route dns` is idempotent; it errors "already exists" which we grep out.
- Caddy's `tls internal` generates certs on first-request — first hit after restart can be slow (~500ms).
- `launchctl load -w` is needed (not just `load`) to override the disabled flag from a previous unload.
- If you edit `Caddyfile.d/*.conf` by hand, `caddy reload --config ./Caddyfile` picks it up without downtime.
- Multi-service projects generate separate launchd plists per sub-service (e.g., `com.assistant.project.market-tracker-stocks.plist`).
- `handle_path` strips the prefix before forwarding. API routes that need the full path use `handle` instead.
