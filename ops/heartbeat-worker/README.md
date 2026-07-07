# ai-server heartbeat worker

External dead-man's-switch for the assistant server. A Cloudflare Worker with a
Cron Trigger polls `https://health.chrispiserchia.com/health` every 5 minutes and
Telegram-DMs you when the server goes dark (and an all-clear when it recovers).

**Why it lives on Cloudflare, not the Mac:** every in-process alerter
(`server-upkeep`, done-DMs, quota alerts) runs *inside* the runner. If the runner
dies, the Mac sleeps, or the tunnel drops, those go silent — and silence looks
identical to health. This Worker runs off-box, so those exact failure modes
produce an alert instead.

## How it works

1. The runner writes `heartbeat:runner` to Redis every loop (`src/runner/main.py`).
2. The web gateway's `GET /health` returns **200** only when that heartbeat is
   fresh (< `runner_heartbeat_stale_seconds`, default 90s) **and** Postgres + Redis
   are reachable; otherwise **503** (`src/gateway/web.py:health`).
3. `Caddyfile.d/health.conf` exposes only `/health` at `health.chrispiserchia.com`.
4. This Worker polls that URL. After `FAILURES_BEFORE_ALERT` (default 2)
   consecutive non-200s it alerts once; it resets + sends an all-clear on recovery.
   State is kept in KV so you get one alert per outage, not one per tick.

## One-time deploy

Requires the Cloudflare account that owns `chrispiserchia.com` and `wrangler`
(`npm install` here first, or use the global CLI).

```bash
cd ops/heartbeat-worker
npm install

# 1. DNS: point health.chrispiserchia.com at the tunnel (same named tunnel as the
#    other subdomains). Add a CNAME health -> <tunnel-id>.cfargotunnel.com, or:
#    cloudflared tunnel route dns ai-server health.chrispiserchia.com

# 2. Create the KV namespace and paste its id into wrangler.toml (kv_namespaces.id)
wrangler kv namespace create HEARTBEAT_KV

# 3. Set the two secrets (reuse the server's bot token + your chat id)
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_CHAT_ID

# 4. Deploy
wrangler deploy
```

## Verify

```bash
# Reload Caddy so the new health vhost is live, then confirm the public URL:
caddy reload --config ../../Caddyfile
curl -s https://health.chrispiserchia.com/health | jq

# Manually trigger one Worker check (fetch handler runs the same logic as cron):
curl -s https://ai-server-heartbeat.<your-subdomain>.workers.dev/ | jq

# Simulate an outage and confirm the Telegram alert after 2 ticks:
launchctl stop com.assistant.runner     # /health flips to 503 within ~90s
wrangler tail                           # watch the scheduled runs
launchctl start com.assistant.runner    # recovery → all-clear DM
```

## Tuning

- `crons` in `wrangler.toml` — poll cadence (default every 5 min).
- `FAILURES_BEFORE_ALERT` — consecutive failures before alerting (default 2).
- `HEALTH_URL` — the endpoint to poll.
