# Containerized sessions (P1)

> How the `isolation: container` tier works, how to enable it, and why it
> exists. Written 2026-07-12 as part of the P1 isolation work.

## The isolation model

Every skill declares an `isolation:` tier in its SKILL.md frontmatter
(default `none`). The runner resolves it per job (`workspaces.resolve_isolation`):

| Tier | cwd | Executor | Who uses it |
|---|---|---|---|
| `none` | canonical checkout | in-process SDK | chat, research-*, atlas-*, ops skills that touch the live system |
| `workspace` | **per-job git clone** under `volumes/workspaces/` | in-process SDK | app-patch, project-evaluate — all code-writing project skills |
| `container` | per-job clone, mounted at `/work` | `claude -p` in docker | server-patch (the riskiest automated lane) |
| `host` | server root, full host | in-process SDK | **god only** — the deliberate break-glass lane so Chris can fix anything from Telegram |

Two independent protections stack here:

1. **Workspace clones** kill the shared-checkout collision class (the
   2026-07-09 single-writer incidents) and let `MAX_CONCURRENT_JOBS=4` run
   safely. Work leaves a workspace only via `git push`; the canonical is
   fast-forwarded afterward (`workspaces.sync_canonical`).
2. **Containers** additionally remove host access entirely for the riskiest
   automated skill: a server-patch session physically cannot restart
   services, touch launchd, read `.env` secrets, or `rm` anything outside
   its clone.

Downgrade rules (logged + audit-evented, never silent): `container` runs as
`workspace` when the runtime is unavailable, the OAuth token is missing, or
the skill needs in-process MCP servers (SDK MCP can't cross the container
boundary).

`god` stays host-native **by design** — that's the phone-fixes-everything
requirement. The tier model's job is to make sure nothing *else* runs bare.

## Enabling the container lane

1. **Install a runtime** (pick one; all expose the `docker` CLI):
   - **colima** (recommended: free, OSS): `brew install colima docker && colima start --cpu 4 --memory 8`
   - OrbStack: faster, free for personal use, `brew install orbstack`
   - Docker Desktop: fine too
2. **Issue a subscription token** (NOT an API key):
   ```bash
   claude setup-token     # opens browser; token is ~1-year-lived
   ```
   Put it in the production `.env`:
   ```
   CONTAINER_RUNTIME=docker
   CLAUDE_CODE_OAUTH_TOKEN=<token from setup-token>
   ```
3. **Build the image**:
   ```bash
   cd "$HOME/Library/Application Support/ai-server"
   docker build -f Dockerfile.agent -t ai-server-agent:latest .
   ```
4. **Smoke-test**:
   ```bash
   docker run --rm -e CLAUDE_CODE_OAUTH_TOKEN ai-server-agent:latest \
     claude -p "say ok" --output-format stream-json --verbose | tail -2
   ```
5. Restart the runner (`/task deploy server` or `launchctl kickstart`).

Nothing else changes: audit logs, Redis streams, review, write-back, and
escalation see identical events from both executors (that parity is tested —
`tests/test_executors.py`).

## Auth rules (INV-3 extended)

- Containers receive `CLAUDE_CODE_OAUTH_TOKEN` only. The executor actively
  strips `ANTHROPIC_API_KEY` from the environment it passes.
- The token lives in `.env` (chmod 600) and is ~1-year-lived; `server-upkeep`
  warns when it's older than 11 months.
- Never bake tokens into `Dockerfile.agent` or the image.

## Known limitations

- **No effort flag on the CLI lane**: the container executor passes
  `--model` but not effort (no stable CLI flag). Container-tier skills trade
  effort tuning for isolation. Revisit when the CLI exposes it.
- **No in-process MCP**: skills tagged `needs-*-mcp` auto-downgrade to
  `workspace`.
- **Linux-in-VM vs macOS**: container sessions build/test in Linux. For the
  server itself (launchd plists, TCC paths) final verification still happens
  at deploy time on the host via `server-deploy`'s pytest gate — the
  container gate is an earlier, cheaper net, not the last one.
- **Network egress is currently open** inside containers (git + npm/pip need
  it). Per-tier egress policy is a deliberate later hardening step.
