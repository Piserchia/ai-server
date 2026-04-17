# Teardown: mac-mini-ai-server

Exact steps to shut down the old system on your Mac Mini. Run these *before*
standing up the new `ai-server` server (so the Telegram bot token frees up and
the Postgres port is available).

**Don't delete the old repo's Docker volumes yet** — keep them for a week as
a safety net in case you need to recover anything.

## 1. Stop whatever is running

### If you were running via launchd:
```bash
cd ~/Documents/mac-mini-ai-server  # or wherever you cloned it
bash scripts/install_launchd.sh uninstall
```

### If you were running via run_native.sh:
```bash
cd ~/Documents/mac-mini-ai-server
bash scripts/run_native.sh stop
```

### If you were running via docker-compose:
```bash
cd ~/Documents/mac-mini-ai-server
docker-compose down
# Don't use -v; keeping the volumes
```

### Kill any zombies:
```bash
pkill -f "src.worker" || true
pkill -f "src.bot_runner" || true
pkill -f "observability.dashboard" || true
```

## 2. Stop the tunnel

If you were running the Cloudflare quick tunnel:
```bash
cd ~/Documents/mac-mini-ai-server
bash scripts/start_tunnel.sh stop
```

Or kill by name:
```bash
pkill -f "cloudflared" || true
```

## 3. Archive the repo

Tag and push so you can recover later if needed:
```bash
cd ~/Documents/mac-mini-ai-server
git add -A
git commit -m "archive: state before rebuild" || true
git tag pre-rebuild-2026-04-16
git push --tags
```

## 4. Free up resources

Check nothing is holding the ports or DB:
```bash
lsof -i :8080   # should be empty
lsof -i :5432   # should show only brew-services postgres if any
lsof -i :6379   # should show only brew-services redis if any
lsof -i :11434  # ollama — should be empty unless you want to keep it

# If Ollama is still running and you don't want it:
brew services stop ollama  # or: pkill ollama
```

## 5. Revoke the GitHub PAT

You shared `ghp_v17JT…H9x` in plaintext during our earlier conversation.
Regardless of what you do next, revoke it now:

1. Go to https://github.com/settings/tokens
2. Find the token and click Delete
3. If any automation depends on it, create a new PAT with narrower scope

## 6. Keep the old repo directory for one week

**Do not** `rm -rf` the old directory yet. Leave it at `~/Documents/mac-mini-ai-server`
for one week as a safety net. After a week of the new server working cleanly:

```bash
# Week from now:
docker-compose down -v     # NOW delete the Docker volumes
rm -rf ~/Documents/mac-mini-ai-server
```

## 7. What to do with running projects during the transition

The old repo has `baseball_bingo.html`, `clock.html`, and some Python toys in its
root. Those come back as new projects in Phase 3 of the new server. Don't
manually copy them — the `new-project` skill will rebuild them cleanly from
descriptions.

**Market-tracker** is in its own repo (`github.com/Piserchia/market-tracker`),
running somewhere on this Mac. It'll be migrated into the new server's
hosting during Phase 3 by registering it as a project and pointing its
`manifest.yml` at the existing repo.

## Done. Now go to GETSTARTED.md.
