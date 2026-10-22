"""
Bash scripts under `scripts/`: syntax-checked with `bash -n` (local, no
network) plus the invariants the launchd timer scripts must never break —
chiefly: NO `pipenv run` in anything launchd runs. pipenv lives in
~/.pyenv/shims, which launchd's `bash -lc` never sees (no ~/.bash_profile;
~/.zprofile is zsh-only); prod's schedule-monitor.log showed
`pipenv: command not found` / rc=127 from 2026-09-14 until the 2026-10-05
repair. `bash -n` cannot catch that; these greps can.

Born in A7 of the Observability Phase 1 re-cut plan
(`docs/superpowers/plans/2026-10-21-observability-phase1-recut.md`). Later
tasks append: B4 and E10 add their timer script to `TIMER_SCRIPTS` in the
commit that creates it; C1 adds the backup/installer/runbook checks; D1
adds `test_seed_schedules_swing_rows_carry_env_required`.

The function-level tests below drive the scripts' bash functions with
fixture files: the function body is extracted by name and sourced into a
throwaway bash with `PROJECT_DIR`/`LOG`/`VENV_PY` pointing at `tmp_path`,
so no probe, DB, Telegram or venv is ever touched.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_scripts_syntax.py -q -p no:cacheprovider
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ALL_SCRIPTS = sorted(p.relative_to(REPO).as_posix() for p in (REPO / "scripts").glob("*.sh"))

# Everything a launchd timer executes (every `install_timer` call in
# scripts/install-launchd.sh). `scripts/codex-canary.sh` is a hand-run
# canary, not a timer, and legitimately uses `pipenv run` — excluded.
TIMER_SCRIPTS = (
    "scripts/backup.sh",
    "scripts/cost-reconcile-run.sh",
    "scripts/healthcheck-all.sh",
    "scripts/schedule-monitor.sh",
)

# The out-of-band alerters (A7; B4 adds the weekly cost-reconcile wrapper):
# `python -m src.notify send` first, the raw Telegram curl as the fallback
# when the CLI itself cannot run.
ALERTER_SCRIPTS = ("scripts/healthcheck-all.sh", "scripts/schedule-monitor.sh",
                   "scripts/cost-reconcile-run.sh")

NOTIFY_SEND = '"$VENV_PY" -m src.notify send'


def _read(rel: str) -> str:
    return (REPO / rel).read_text()


def _bash_function(rel: str, name: str) -> str:
    """The text of `name() { … }` from the script (top-level function, closed
    by a `}` at column 0)."""
    src = _read(rel)
    m = re.search(rf"^{re.escape(name)}\(\) \{{.*?^\}}", src, re.S | re.M)
    assert m, f"{rel}: no top-level bash function {name}()"
    return m.group(0)


def _run_function(rel: str, name: str, call: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    script = _bash_function(rel, name) + "\n" + call + "\n"
    full_env = {**os.environ, **env}
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=full_env)


# --- syntax ----------------------------------------------------------------


def test_scripts_dir_has_shell_scripts():
    assert ALL_SCRIPTS, "scripts/*.sh glob is empty — the parametrized checks below would be vacuous"


@pytest.mark.parametrize("rel", ALL_SCRIPTS)
def test_bash_syntax(rel):
    r = subprocess.run(["bash", "-n", str(REPO / rel)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# --- launchd timer invariants ----------------------------------------------


@pytest.mark.parametrize("rel", TIMER_SCRIPTS)
def test_timer_scripts_never_use_pipenv_run(rel):
    src = _read(rel)
    assert "pipenv run" not in src, f"{rel}: launchd has no pipenv on PATH (rc=127)"


def test_every_timer_script_in_install_launchd_is_listed():
    # The list above cannot drift from what launchd actually runs: every
    # `install_timer "<label>" "scripts/<x>.sh"` call must name a listed script.
    src = _read("scripts/install-launchd.sh")
    installed = re.findall(r'^install_timer\s+"[^"]+"\s+"(scripts/[^"]+)"', src, re.M)
    assert installed, "no install_timer calls found in scripts/install-launchd.sh"
    missing = sorted(set(installed) - set(TIMER_SCRIPTS))
    assert missing == [], f"timer scripts installed by launchd but not in TIMER_SCRIPTS: {missing}"
    for rel in TIMER_SCRIPTS:
        assert (REPO / rel).is_file(), rel


def test_schedule_monitor_collector_runs_on_venv_python():
    # The line that was `pipenv: command not found` on prod from 2026-09-14.
    src = _read("scripts/schedule-monitor.sh")
    assert '"$VENV_PY" -m src.runner.schedule_adherence' in src


# --- alerters: notify send first, curl fallback ----------------------------


def test_alerters_prefer_notify_send_with_curl_fallback():
    for rel in ALERTER_SCRIPTS:
        src = _read(rel)
        assert NOTIFY_SEND in src, rel                          # never `pipenv run python`
        assert "api.telegram.org" in src, rel                   # fallback kept
        assert src.index(NOTIFY_SEND) < src.index("api.telegram.org"), (
            f"{rel}: the notify CLI must be tried before the raw curl"
        )


def test_healthcheck_resolves_and_guards_the_interpreter():
    # healthcheck-all.sh gains its first python call here (notify_send); same
    # VENV_PY contract as schedule-monitor: plist env first, `pipenv --venv`
    # next, and a guard that the interpreter can import the server.
    src = _read("scripts/healthcheck-all.sh")
    assert 'VENV_PY="${VENV_PY:-' in src
    assert "pipenv --venv" in src
    assert "import src.config" in src
    # the guard and the pipenv probe both cd first: this script never cd's,
    # and the editable install is inert under ~/Documents (hidden-.pth gotcha)
    assert re.search(r'\(cd "\$PROJECT_DIR" && "\$VENV_PY" -c .import src\.config.\)', src)


def test_healthcheck_curl_blocks_are_fallbacks_only():
    # Both alert sites: `if notify_send … ; then … elif curl … ; then` — the
    # curl is never the first branch any more.
    src = _read("scripts/healthcheck-all.sh")
    assert src.count("if notify_send ops_alert") == 2, "runner-down and swing-watchdog both go through notify_send"
    assert src.count("elif curl -sf --max-time 10") == 2
    assert not re.search(r"^\s*if curl -sf --max-time 10", src, re.M)


def test_schedule_monitor_send_dm_tries_notify_first():
    fn = _bash_function("scripts/schedule-monitor.sh", "send_dm")
    assert NOTIFY_SEND in fn
    assert "--kind ops_alert" in fn and "--severity warn" in fn
    assert fn.index(NOTIFY_SEND) < fn.index("api.telegram.org")
    assert "TELEGRAM_ALLOWED_CHAT_IDS" in fn        # read-only, for the fallback


def _run_functions(rel: str, names: tuple[str, ...], call: str,
                   env: dict[str, str]) -> subprocess.CompletedProcess:
    script = "\n".join(_bash_function(rel, n) for n in names) + "\n" + call + "\n"
    full_env = {**os.environ, **env}
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=full_env)


class TestNotifySendFunction:
    """`notify_send()` in healthcheck-all.sh, driven with a fake interpreter.
    `resolve_venv_py()` is sourced beside it: the interpreter is resolved
    lazily on the first send (whole-tier review 2026-10-22), memoised, and a
    VENV_PY handed in by the plist env is still import-guarded."""

    REL = "scripts/healthcheck-all.sh"
    FNS = ("resolve_venv_py", "notify_send")

    def _fake_python(self, tmp_path: Path, rc: int) -> Path:
        fake = tmp_path / "fake-python"
        fake.write_text(
            "#!/bin/bash\n"
            f"printf '%s\\n' \"$@\" > '{tmp_path}/argv.txt'\n"
            f"printf '%s\\n' \"$PWD\" > '{tmp_path}/cwd.txt'\n"
            f"exit {rc}\n"
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        return fake

    def test_no_interpreter_returns_1_without_running_anything(self, tmp_path):
        r = _run_functions(self.REL, self.FNS, 'notify_send ops_alert "hi"; echo "rc=$?"',
                           {"VENV_PY": "", "PROJECT_DIR": str(tmp_path), "LOG": str(tmp_path / "log"),
                            "HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
        assert "rc=1" in r.stdout
        assert not (tmp_path / "argv.txt").exists()
        assert "WARN no project venv python found" in (tmp_path / "log").read_text()

    def test_delivered_returns_0_with_the_cli_argv(self, tmp_path):
        fake = self._fake_python(tmp_path, rc=0)
        r = _run_functions(self.REL, self.FNS, 'notify_send ops_alert "runner down: x"; echo "rc=$?"',
                           {"VENV_PY": str(fake), "PROJECT_DIR": str(tmp_path), "LOG": str(tmp_path / "log")})
        assert "rc=0" in r.stdout, r.stderr
        argv = (tmp_path / "argv.txt").read_text().splitlines()
        assert argv == ["-m", "src.notify", "send", "--kind", "ops_alert",
                        "--severity", "critical", "--text", "runner down: x"]
        # runs from the project root (the editable install is inert elsewhere)
        assert (tmp_path / "cwd.txt").read_text().strip() == str(tmp_path)

    def test_cli_failure_returns_1_so_the_caller_takes_curl(self, tmp_path):
        fake = self._fake_python(tmp_path, rc=1)
        r = _run_functions(self.REL, self.FNS, 'notify_send ops_alert "x"; echo "rc=$?"',
                           {"VENV_PY": str(fake), "PROJECT_DIR": str(tmp_path), "LOG": str(tmp_path / "log")})
        assert "rc=1" in r.stdout


def _venv_block(rel: str) -> str:
    """The top-level interpreter-resolution block of a timer script: from the
    `VENV_PY="${VENV_PY:-}"` line to the `fi` that closes it (column 0)."""
    src = _read(rel)
    m = re.search(r'^VENV_PY="\$\{VENV_PY:-\}"\n.*?^fi\n', src, re.S | re.M)
    assert m, f"{rel}: no VENV_PY resolution block"
    return m.group(0)


class TestVenvResolution:
    """The `~/.local/share/virtualenvs/<basename>-*` fallback of the three
    timer scripts selects the venv whose pipenv-written `.project` equals
    PROJECT_DIR (whole-tier review 2026-10-22): on this host the dev and the
    prod checkout share the basename `ai-server`, and the old first-match glob
    picked the DEV venv (`ai-server-SOXcmoRD` sorts before prod's
    `ai-server-bpzo5SVu`) for prod's timers. First-match survives only as a
    LOGGED fallback. Fixture: HOME=tmp with two venv dirs, the lexically
    FIRST one belonging to another checkout; PATH without pipenv."""

    SCRIPTS = ("scripts/healthcheck-all.sh", "scripts/schedule-monitor.sh",
               "scripts/cost-reconcile-run.sh")

    def _fixture(self, tmp_path: Path, *, match: bool) -> dict[str, str]:
        project = tmp_path / "server"
        project.mkdir()
        other = tmp_path / "elsewhere" / "server"
        for name, owner in (("server-AAAA", other), ("server-BBBB", project if match else other)):
            d = tmp_path / ".local/share/virtualenvs" / name
            (d / "bin").mkdir(parents=True)
            py = d / "bin/python"
            py.write_text("#!/bin/bash\nexit 0\n")        # `-c 'import src.config'` succeeds
            py.chmod(py.stat().st_mode | stat.S_IXUSR)
            (d / ".project").write_text(f"{owner}\n")       # pipenv writes a trailing newline
        return {"HOME": str(tmp_path), "PROJECT_DIR": str(project), "LOG": str(tmp_path / "log"),
                "VENV_PY": "", "PATH": "/usr/bin:/bin"}

    def _resolve(self, rel: str, env: dict[str, str]) -> subprocess.CompletedProcess:
        if rel == "scripts/healthcheck-all.sh":
            return _run_function(rel, "resolve_venv_py", 'resolve_venv_py; echo "VENV_PY=$VENV_PY"', env)
        script = _venv_block(rel) + '\necho "VENV_PY=$VENV_PY"\n'
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                              env={**os.environ, **env})

    @pytest.mark.parametrize("rel", SCRIPTS)
    def test_project_match_beats_first_match(self, tmp_path, rel):
        env = self._fixture(tmp_path, match=True)
        r = self._resolve(rel, env)
        assert f"VENV_PY={tmp_path}/.local/share/virtualenvs/server-BBBB/bin/python" in r.stdout, r.stderr
        assert "WARN" not in Path(env["LOG"]).read_text() if Path(env["LOG"]).exists() else True

    @pytest.mark.parametrize("rel", SCRIPTS)
    def test_no_project_match_falls_back_to_first_match_and_logs(self, tmp_path, rel):
        env = self._fixture(tmp_path, match=False)
        r = self._resolve(rel, env)
        assert f"VENV_PY={tmp_path}/.local/share/virtualenvs/server-AAAA/bin/python" in r.stdout, r.stderr
        log = Path(env["LOG"]).read_text()
        assert "WARN no venv whose .project matches" in log and "server-AAAA" in log

    @pytest.mark.parametrize("rel", SCRIPTS)
    def test_source_pins(self, rel):
        src = _read(rel)
        assert '.project' in src and 'first' in src
        assert "WARN no venv whose .project matches $PROJECT_DIR" in src

    def test_healthcheck_resolves_lazily_and_memoises(self, tmp_path):
        # the 5-min tick must not spawn the interpreter when nothing is sent,
        # and a second notify_send must not resolve again
        src = _read("scripts/healthcheck-all.sh")
        fn = _bash_function("scripts/healthcheck-all.sh", "notify_send")
        assert "resolve_venv_py" in fn
        assert "_VENV_RESOLVED=1" in _bash_function("scripts/healthcheck-all.sh", "resolve_venv_py")
        # no top-level import probe outside the function (prose may mention it)
        top = src.replace(_bash_function("scripts/healthcheck-all.sh", "resolve_venv_py"), "")
        assert "-c 'import src.config'" not in top
        env = self._fixture(tmp_path, match=True)
        r = _run_function("scripts/healthcheck-all.sh", "resolve_venv_py",
                          'resolve_venv_py; a="$VENV_PY"; VENV_PY=""; resolve_venv_py; echo "second=$VENV_PY"; echo "first=$a"',
                          env)
        out = r.stdout
        assert "first=" in out and out.split("first=")[1].strip().endswith("server-BBBB/bin/python")
        assert "second=\n" in out        # memoised: the second call did not resolve again


class TestCountScheduleDeferred:
    """`count_schedule_deferred()` in schedule-monitor.sh counts D1's
    `schedule_deferred` records under volumes/audit_log/schedules/ written in
    the last 24 h — the out-of-band second signal for a deferred row."""

    REL = "scripts/schedule-monitor.sh"

    @staticmethod
    def _rec(kind: str, hours_ago: float) -> str:
        ts = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")
        return json.dumps({"ts": ts, "job_id": "sched-1", "kind": kind, "reason": "provisioning_gap"})

    def _count(self, tmp_path: Path) -> str:
        r = _run_function(self.REL, "count_schedule_deferred", "count_schedule_deferred",
                          {"PROJECT_DIR": str(tmp_path), "LOG": str(tmp_path / "log")})
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()

    def test_missing_directory_counts_zero(self, tmp_path):
        assert self._count(tmp_path) == "0"

    def test_counts_only_recent_deferrals_in_the_schedules_subdir(self, tmp_path):
        sched = tmp_path / "volumes/audit_log/schedules"
        sched.mkdir(parents=True)
        (sched / "a.jsonl").write_text("\n".join([
            self._rec("schedule_deferred", 1),      # counted
            self._rec("schedule_deferred", 23),     # counted
            self._rec("schedule_deferred", 30),     # too old
            self._rec("note", 1),                   # other kind
        ]) + "\n")
        (sched / "b.jsonl").write_text(self._rec("schedule_deferred", 2) + "\n")
        # a top-level job log mentioning the kind is NOT a schedule stream
        (tmp_path / "volumes/audit_log/job.jsonl").write_text(self._rec("schedule_deferred", 1) + "\n")
        assert self._count(tmp_path) == "3"


# --- B4: the weekly cost-reconcile timer --------------------------------------


def test_cost_reconcile_timer_installed():
    # D-P1-8: a launchd timer, not a schedule row. Monday 07:30 local, through
    # the existing 3-arg `install_timer` helper (label, script, interval block).
    src = _read("scripts/install-launchd.sh")
    m = re.search(r'^install_timer "cost-reconcile" "scripts/cost-reconcile-run\.sh" \\\n\s*"(.*)"$', src, re.M)
    assert m, "install-launchd.sh has no install_timer call for cost-reconcile"
    block = m.group(1)
    assert "<key>StartCalendarInterval</key>" in block
    assert "<key>Weekday</key><integer>1</integer>" in block
    assert "<key>Hour</key><integer>7</integer>" in block
    assert "<key>Minute</key><integer>30</integer>" in block
    # … and the installer still only installs listed timer scripts (cross-check above).
    assert "scripts/cost-reconcile-run.sh" in TIMER_SCRIPTS


def test_cost_reconcile_wrapper_runs_the_cli_with_both_windows_the_db_leg_and_the_seed():
    run_src = _read("scripts/cost-reconcile-run.sh")
    assert "pipenv run" not in run_src
    assert '"$VENV_PY" scripts/cost-reconcile.py' in run_src
    assert "--windows 30,7" in run_src and "--db" in run_src and "--seed-lane-budgets" in run_src
    assert "volumes/logs/cost-reconcile.log" in run_src
    # `cd "$PROJECT_DIR"` comes BEFORE the first VENV_PY= assignment: the
    # editable install is inert under ~/Documents, and `pipenv --venv` finds
    # the Pipfile by cwd.
    assert run_src.index('cd "$PROJECT_DIR"') < run_src.index("VENV_PY=")
    assert 'VENV_PY="${VENV_PY:-' in run_src and "pipenv --venv" in run_src
    assert "import src.config" in run_src
    # a non-zero exit is alerted through notify send (severity warn), curl fallback
    assert "--kind ops_alert" in run_src and "--severity warn" in run_src
    assert "5-minute cache writes" in run_src                   # the rc=1 message
    # rc=1 is the CLI's RESERVED credits-signature code (review round 1): the
    # billing DM is gated on exactly 1, and the generic branch names rc=3 (the
    # run itself failed — DB leg down) so a Postgres outage never reads as a
    # usage-credit overflow.
    assert "if (( rc == 1 )); then" in run_src
    assert "3 = the run itself failed" in run_src
    assert "FATAL" in run_src                                   # no-venv is logged, never silent
    assert os.access(REPO / "scripts/cost-reconcile-run.sh", os.X_OK)
    assert os.access(REPO / "scripts/cost-reconcile.py", os.X_OK)


class TestCostReconcileAlert:
    """`send_alert()` in cost-reconcile-run.sh, driven with a fake interpreter:
    notify send first (argv pinned), the curl fallback only when it fails."""

    REL = "scripts/cost-reconcile-run.sh"

    def _fake_python(self, tmp_path: Path, rc: int) -> Path:
        fake = tmp_path / "fake-python"
        fake.write_text(
            "#!/bin/bash\n"
            f"printf '%s\\n' \"$@\" > '{tmp_path}/argv.txt'\n"
            f"printf '%s\\n' \"$PWD\" > '{tmp_path}/cwd.txt'\n"
            f"exit {rc}\n"
        )
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        return fake

    def test_delivered_via_notify_with_the_cli_argv(self, tmp_path):
        fake = self._fake_python(tmp_path, rc=0)
        log = tmp_path / "log"
        r = _run_function(self.REL, "send_alert", 'send_alert "cost-reconcile: x"; echo "rc=$?"',
                          {"VENV_PY": str(fake), "PROJECT_DIR": str(tmp_path), "LOG": str(log)})
        assert "rc=0" in r.stdout, r.stderr
        argv = (tmp_path / "argv.txt").read_text().splitlines()
        assert argv == ["-m", "src.notify", "send", "--kind", "ops_alert",
                        "--severity", "warn", "--text", "cost-reconcile: x"]
        assert (tmp_path / "cwd.txt").read_text().strip() == str(tmp_path)
        assert "ALERT sent via notify" in log.read_text()

    def test_cli_failure_without_creds_is_logged_not_fatal(self, tmp_path):
        fake = self._fake_python(tmp_path, rc=1)
        log = tmp_path / "log"
        # no .env → the curl fallback has no creds → WARN line, rc 0 (never aborts the wrapper)
        r = _run_function(self.REL, "send_alert", 'send_alert "x"; echo "rc=$?"',
                          {"VENV_PY": str(fake), "PROJECT_DIR": str(tmp_path), "LOG": str(log)})
        assert "rc=0" in r.stdout, r.stderr
        assert "creds missing" in log.read_text()


def test_schedule_monitor_reports_deferrals_as_a_finding():
    src = _read("scripts/schedule-monitor.sh")
    assert "count_schedule_deferred" in src
    assert "volumes/audit_log/schedules" in src
    assert "FINDING deferred:" in src


# --- C1: backup.sh (atlas dump, sealed secrets, retention), restore-drill.sh,
#         install-launchd.sh (timer env block, timers-only, plist escaping),
#         the Phase-1 ops-hygiene runbook ----------------------------------------

RUNBOOK = "docs/runbooks/2026-10-21-phase1-ops-hygiene.md"


def test_backup_dumps_atlas_and_seals_secrets():
    src = _read("scripts/backup.sh")
    # D-P1-6: a custom-format atlas dump OUTSIDE the nightly tarball, only when
    # the database exists, never fatal, size logged.
    # one query, no `psql -lqt | … | grep -q` pipeline (pipefail + grep -q
    # SIGPIPE hazard — whole-tier review 2026-10-22)
    assert "SELECT 1 FROM pg_database WHERE datname = 'atlas'" in src
    assert "psql -lqt" not in src
    assert 'pg_dump -Fc atlas > "$BACKUP_DIR/atlas-$STAMP.dump"' in src
    assert "atlas dump OK" in src and "WARN atlas dump failed" in src
    # the sealed bundle: .env, the atlas CANONICAL .env (the dev clone, the
    # file provision_env_files copies), the cloudflared trio
    assert "openssl enc -aes-256-cbc -pbkdf2 -iter 200000" in src
    assert 'SEAL_KEY="${BACKUP_SEAL_KEY:-$HOME/.config/ai-server/backup-seal.key}"' in src
    assert "seal SKIP" in src
    assert "secrets.tar.enc" in src
    assert "Documents/repos/atlas/.env" in src
    assert ".cloudflared" in src
    # the plain .env never lands in the tarball tree; it is copied into the
    # seal staging dir only, and only the encrypted bundle reaches $TMP
    assert 'cp "$PROJECT_DIR/.env" "$TMP/' not in src
    assert 'cp "$PROJECT_DIR/.env" "$SEAL_TMP/secrets/env"' in src
    # the OK line names the three sources; a source that did not land is a
    # PARTIAL line (the cp's are `|| true` and tar+openssl seal an empty tree)
    assert "sealed secrets OK (env, atlas.env, cloudflared)" in src
    assert "WARN sealed secrets PARTIAL (missing:$missing)" in src
    assert '-s "$SEAL_TMP/secrets/atlas.env"' in src
    assert '-s "$SEAL_TMP/secrets/cloudflared/config.yml"' in src
    # an EXIT trap: a killed run never leaves db.sql or plaintext secret
    # copies under $TMPDIR
    assert "trap 'rm -rf \"$TMP\" \"${SEAL_TMP:-}\"' EXIT" in src
    # off-site: the tarball nightly, the atlas dump on Sundays only
    assert "date -u +%u" in src
    assert "pipenv" not in src
    # the header was written for a 2 TB disk; this host has 228 GB
    assert "2TB" not in src and "2 TB" not in src


def test_backup_has_retention_rule():
    src = _read("scripts/backup.sh")
    assert "--min-age 60d" in src                          # off-site tarballs
    assert "-mtime +60" in src                             # local tarballs
    assert "-mtime +7" in src                              # local atlas dumps (D-P1-6)
    assert "--min-age 35d --include 'atlas-*'" in src      # off-site atlas dumps
    assert "No retention cap" not in src                   # the old comment is gone


def test_restore_drill_exists_and_parses():
    rel = "scripts/restore-drill.sh"
    r = subprocess.run(["bash", "-n", str(REPO / rel)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert os.access(REPO / rel, os.X_OK)
    src = _read(rel)
    assert "restore_drill_assistant" in src and "restore_drill_atlas" in src
    assert "pg_restore" in src                              # the -Fc atlas dump
    assert "dropdb --if-exists" in src
    assert "openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000" in src
    assert "pipenv" not in src
    # the drill prepends nothing to PATH: the operator's shell (and a test's
    # fake pg tools) win over the Homebrew dirs appended for bare launchd-ish shells
    assert 'export PATH="$PATH:' in src


class TestRestoreDrill:
    """`scripts/restore-drill.sh` driven end to end with fake Postgres tools on
    PATH (createdb/dropdb/psql/pg_restore/rclone record their argv and answer
    the drill's three queries), a fixture tarball, a fixture `atlas-*.dump`
    and a REAL sealed bundle (openssl, throwaway key). No live database."""

    REL = "scripts/restore-drill.sh"

    FAKE = r'''#!/bin/bash
# fake pg tool: log argv, answer the drill's queries from env
me=$(basename "$0")
printf '%s %s\n' "$me" "$*" >> "$FAKE_LOG"
case "$me" in
  psql)
    if [[ "$1" == "-tAc" ]]; then
      q="$2"
      case "$q" in
        *"FROM jobs"*) echo "${FAKE_JOBS:-42}" ;;
        *information_schema.tables*) echo "public.candles" ;;
        *"FROM public.candles"*) echo "7" ;;
        *) echo 0 ;;
      esac
    fi
    exit 0 ;;
  rclone) exit 1 ;;
  *) exit 0 ;;
esac
'''

    def _setup(self, tmp_path: Path, *, with_key=True, with_dump=True, with_bundle=True,
               with_atlas_env=True, jobs="42") -> dict[str, str]:
        fake_bin = tmp_path / "bin"
        fake_bin.mkdir()
        for tool in ("createdb", "dropdb", "psql", "pg_restore", "rclone"):
            p = fake_bin / tool
            p.write_text(self.FAKE)
            p.chmod(p.stat().st_mode | stat.S_IXUSR)
        root = tmp_path / "server"
        (root / "volumes/backups").mkdir(parents=True)
        (root / "volumes/logs").mkdir(parents=True)
        stage = tmp_path / "stage"
        stage.mkdir()
        (stage / "db.sql").write_text("-- fixture dump\nCREATE TABLE jobs (id text);\n")
        key = tmp_path / "seal.key"
        key.write_text("fixture-seal-key\n")
        if with_bundle:
            sec = tmp_path / "secrets"
            (sec / "cloudflared").mkdir(parents=True)
            (sec / "env").write_text("TELEGRAM_BOT_TOKEN=fixture-not-a-secret\n")
            if with_atlas_env:
                (sec / "atlas.env").write_text("DATABASE_URL=fixture-not-a-secret\n")
            (sec / "cloudflared/config.yml").write_text("tunnel: fixture\n")
            subprocess.run(["tar", "-cf", str(tmp_path / "secrets.tar"), "-C", str(tmp_path), "secrets"], check=True)
            subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt",
                            "-in", str(tmp_path / "secrets.tar"), "-out", str(stage / "secrets.tar.enc"),
                            "-pass", f"file:{key}"], check=True)
        subprocess.run(["tar", "-czf", str(root / "volumes/backups/backup-2026-10-21.tar.gz"),
                        "-C", str(stage), "."], check=True)
        if with_dump:
            (root / "volumes/backups/atlas-2026-10-21.dump").write_bytes(b"PGDMP fixture")
        # the script resolves PROJECT_DIR from its own location → copy it into the fixture tree
        (root / "scripts").mkdir()
        target = root / "scripts/restore-drill.sh"
        target.write_text(_read(self.REL))
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        env = {
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "FAKE_LOG": str(tmp_path / "calls.log"),
            "FAKE_JOBS": jobs,
            "BACKUP_SEAL_KEY": str(key if with_key else tmp_path / "no-such-key"),
            "HOME": str(tmp_path),
        }
        return {"script": str(target), "root": str(root), "calls": str(tmp_path / "calls.log"), **env}

    def _run(self, cfg: dict[str, str]) -> subprocess.CompletedProcess:
        env = {k: v for k, v in cfg.items() if k in ("PATH", "FAKE_LOG", "FAKE_JOBS", "BACKUP_SEAL_KEY", "HOME")}
        return subprocess.run(["bash", cfg["script"]], capture_output=True, text=True, env=env)

    def test_pass_on_both_db_legs_unseals_the_bundle_and_drops_the_throwaways(self, tmp_path):
        cfg = self._setup(tmp_path)
        r = self._run(cfg)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "PASS assistant restore: 42 jobs" in r.stdout
        assert "PASS atlas restore: public.candles 7 rows" in r.stdout
        assert "PASS sealed secrets: 5 entries" in r.stdout            # names counted, never printed
        assert "sealed bundle lacks" not in r.stdout                   # env, atlas.env, cloudflared all present
        assert "fixture-not-a-secret" not in r.stdout + r.stderr       # a value never leaks
        assert "WARN off-site" in r.stdout                             # rclone r2: not configured
        assert r.stdout.rstrip().endswith("PASS")
        calls = Path(cfg["calls"]).read_text()
        assert "pg_restore" in calls and "restore_drill_atlas" in calls
        assert "dropdb --if-exists restore_drill_assistant" in calls
        assert "dropdb --if-exists restore_drill_atlas" in calls
        log = (Path(cfg["root"]) / "volumes/logs/backup.log").read_text()
        assert "restore-drill backup-2026-10-21.tar.gz result=PASS" in log

    def test_first_run_shape_db_legs_pass_with_two_warns(self, tmp_path):
        # the §6 Deltas' first-run expectation on this host: no seal key yet,
        # no r2 remote → PASS with WARNs, exit 0 (the WARNs are the owner's §7 rows)
        cfg = self._setup(tmp_path, with_key=False)
        r = self._run(cfg)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "PASS assistant restore" in r.stdout and "PASS atlas restore" in r.stdout
        assert "WARN sealed bundle present but no seal key" in r.stdout
        assert "WARN off-site" in r.stdout
        assert r.stdout.rstrip().endswith("PASS")

    def test_bundle_without_atlas_env_warns_but_passes(self, tmp_path):
        # whole-tier review 2026-10-22: the drill names the other two sources
        # too (atlas.env, cloudflared) — WARN, not FAIL, so a host without the
        # atlas dev clone or a tunnel still passes; backup.sh logged PARTIAL.
        cfg = self._setup(tmp_path, with_atlas_env=False)
        r = self._run(cfg)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "PASS sealed secrets: 4 entries" in r.stdout
        assert "WARN sealed bundle lacks secrets/atlas.env" in r.stdout
        assert "WARN sealed bundle lacks secrets/cloudflared/config.yml" not in r.stdout
        assert r.stdout.rstrip().endswith("PASS")

    def test_atlas_table_identifier_is_quoted(self):
        # a mixed-case or reserved table name must not yield `?` rows: the
        # drill asks Postgres for a format('%I.%I') identifier
        src = _read(self.REL)
        assert "format('%I.%I', table_schema, table_name)" in src
        assert "table_schema||'.'||table_name" not in src

    def test_missing_dump_and_bundle_are_warns_not_fails(self, tmp_path):
        cfg = self._setup(tmp_path, with_dump=False, with_bundle=False)
        r = self._run(cfg)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "WARN atlas dump absent" in r.stdout
        assert "WARN no sealed secrets in this backup" in r.stdout

    def test_zero_jobs_is_a_fail(self, tmp_path):
        cfg = self._setup(tmp_path, jobs="0")
        r = self._run(cfg)
        assert r.returncode == 1
        assert "FAIL assistant restore" in r.stdout
        assert r.stdout.rstrip().endswith("FAIL")
        log = (Path(cfg["root"]) / "volumes/logs/backup.log").read_text()
        assert "result=FAIL" in log

    def test_no_tarball_is_a_fail(self, tmp_path):
        cfg = self._setup(tmp_path)
        Path(cfg["root"], "volumes/backups/backup-2026-10-21.tar.gz").unlink()
        r = self._run(cfg)
        assert r.returncode == 1
        assert "FAIL no backup tarball" in r.stdout


def test_installer_timer_plists_carry_venv_env():
    src = _read("scripts/install-launchd.sh")
    # `timers-only`: re-render the timers without unload/load of runner/web/bot
    assert "timers-only" in src
    assert "if (( ! TIMERS_ONLY )); then" in src
    timer_fn = _bash_function("scripts/install-launchd.sh", "install_timer")
    assert "<key>EnvironmentVariables</key>" in timer_fn
    assert "<string>${VENV_DIR}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>" in timer_fn
    assert "<key>VENV_PY</key><string>${VENV_DIR}/bin/python</string>" in timer_fn
    assert "<key>DISABLE_ERROR_REPORTING</key><string>1</string>" in timer_fn
    assert "<key>DISABLE_TELEMETRY</key><string>1</string>" in timer_fn
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in src                  # never a credential in a plist


def test_installer_uninstall_removes_every_timer():
    # whole-tier review 2026-10-22: `uninstall` used to remove only the three
    # services + sync-learnings; the timers stayed loaded and kept firing.
    src = _read("scripts/install-launchd.sh")
    installed = re.findall(r'^install_timer "([a-z-]+)"', src, re.M)
    m = re.search(r"^TIMER_LABELS=\(([^)]*)\)", src, re.M)
    assert m, "TIMER_LABELS array missing"
    assert sorted(m.group(1).split()) == sorted(installed) == sorted(
        ["backup", "healthcheck-all", "schedule-monitor", "cost-reconcile"])
    un = _bash_function("scripts/install-launchd.sh", "uninstall")
    assert 'for t in "${TIMER_LABELS[@]}"' in un and '"${timers[@]}"' in un


def _installer_plist_bodies() -> list[str]:
    src = _read("scripts/install-launchd.sh")
    bodies = re.findall(r"<< PLIST\n(.*?)\nPLIST\n", src, re.S)
    assert len(bodies) == 3, "services loop, sync-learnings timer, install_timer"
    return bodies


def test_installer_escapes_ampersands():
    # 10 of 14 prod plists failed `plutil -p` on 2026-10-21: a raw `&&` inside
    # a <string> is not XML. Every ProgramArguments string must carry
    # `&amp;&amp;`, and each heredoc must parse as XML once the shell
    # expansions are replaced by a placeholder.
    import xml.etree.ElementTree as ET
    for body in _installer_plist_bodies():
        assert "&&" not in body, body
        assert "&amp;&amp;" in body
        rendered = re.sub(r"\$\{[A-Za-z_0-9]+\}|\$[0-9A-Za-z_]+", "X", body)
        ET.fromstring(rendered)                                  # raises on raw `&`


def test_runbook_exists():
    doc = _read(RUNBOOK)
    for needle in (
        # §0 entry probes
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/api/jobs",
        "plutil -p ~/Library/LaunchAgents/com.assistant.*.plist | grep -c CLAUDE_CODE_OAUTH_TOKEN",
        # §1 power, §2 R2, §3 seal key, §4 drill, §5 timers
        "sudo pmset -a autorestart 1",
        "ai-server-backups", "rclone config", "--min-age 60d", "--min-age 35d",
        "mkdir -p ~/.config/ai-server", "openssl rand -base64 48", "backup-seal.key", "chmod 600",
        "restore-drill.sh", "atlas dump OK",
        "bash scripts/install-launchd.sh timers-only",
        # §6 Ollama (spec D5 = yes; the pull / keep-alive settings are Phase 4)
        "ollama rm", "phi3:mini", "deepseek-coder-v2:16b", "mistral", "OLLAMA_MAX_LOADED_MODELS",
        # §7 D4 confirmations, §8 bingo's hook
        "Help improve Claude", "baseball-bingo",
    ):
        assert needle in doc, needle
    # the reviewed spec forbids a token in the launchd env (P0 runbook, round-1 #31)
    assert "into the launchd env" not in doc
    assert "pipenv run" not in doc


# --- D1: the four swing rows declare their Tradier key (D-P1-7) ---------------


def test_seed_schedules_swing_rows_carry_env_required():
    src = _read("scripts/seed-schedules.sh")
    want = '\'{"project_slug":"atlas","env_required":["TRADIER_SANDBOX_TOKEN"]}\''
    rows = {}
    for m in re.finditer(r"^upsert '([^']+)'.*$", src, re.M):
        rows[m.group(1)] = m.group(0)
    for name in ("atlas-swing-supervise-edt", "atlas-swing-supervise-est",
                 "atlas-swing-trade-edt", "atlas-swing-trade-est"):
        assert name in rows, f"{name} missing from seed-schedules.sh"
        assert rows[name].rstrip().endswith(want), f"{name} payload is not exactly {want}"
    # The research row keeps its timeout payload; the governor has none;
    # the value rows are untouched.
    assert rows["atlas-swing-research"].rstrip().endswith(
        '\'{"project_slug":"atlas","session_timeout_seconds":3600}\'')
    assert "env_required" not in rows["atlas-swing-evaluate"]
    assert "env_required" not in rows["atlas-value-monitor"]
    assert src.count('"env_required":[') == 4      # the four rows, nothing else
