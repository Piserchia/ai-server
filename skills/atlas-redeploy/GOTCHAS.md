# atlas-redeploy GOTCHAS

## Runtime CHANGELOG.md pollution (2026-07-09)

A previous `atlas-redeploy` run (or another skill acting under CLAUDE.md's
"update CHANGELOG.md for every module you touched" instruction) wrote a
deploy-audit entry directly into `projects/atlas/CHANGELOG.md` — the runtime
clone. This caused the next `git pull --ff-only` to refuse with:

```
error: Your local changes to the following files would be overwritten by merge:
    CHANGELOG.md
```

**Root cause**: CLAUDE.md says "Update CHANGELOG.md for every module you
touched." A skill instance confused "module" with the atlas project itself and
wrote to the runtime clone instead of the ai-server's own CHANGELOG. The
runtime clone is **read-only** per this skill's hard rules.

**Fix for humans**:
```bash
cd "$HOME/Library/Application Support/ai-server/projects/atlas"
git branch backup-$(date +%Y%m%d)
git checkout -- CHANGELOG.md
```
Then re-trigger the redeploy.

**Prevention**: Never write to any file in `projects/atlas/` during a redeploy
run. When the CLAUDE.md write-back instruction fires at conversation end, write
to `skills/atlas-redeploy/CHANGELOG.md` or the ai-server's top-level
`CHANGELOG.md`, NOT the atlas project's CHANGELOG.

## swing/value venvs need tradingcore installed separately (2026-08-31)

`swing` and `value` depend on `tradingcore` as a peer package (not listed in
their `pyproject.toml` dependencies — stdlib+pyyaml-only ceiling). When their
venvs are freshly created (`self-heal` path), running `pytest` immediately fails
with `ModuleNotFoundError: No module named 'tradingcore'`.

**Fix**: after creating the swing or value venv (or after tradingcore changes),
install tradingcore into it explicitly:

```bash
cd "$ATLAS/swing"
.venv/bin/pip install -q -e "../tradingcore"

cd "$ATLAS/value"
.venv/bin/pip install -q -e "../tradingcore"
```

The manifest gates for swing and value use `when_paths: ["swing/", "tradingcore/"]`
and `["value/", "tradingcore/"]` — so this fix is needed whenever tradingcore
itself changes too.
