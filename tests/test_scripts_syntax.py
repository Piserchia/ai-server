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


class TestNotifySendFunction:
    """`notify_send()` in healthcheck-all.sh, driven with a fake interpreter."""

    REL = "scripts/healthcheck-all.sh"

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
        r = _run_function(self.REL, "notify_send", 'notify_send ops_alert "hi"; echo "rc=$?"',
                          {"VENV_PY": "", "PROJECT_DIR": str(tmp_path), "LOG": str(tmp_path / "log")})
        assert "rc=1" in r.stdout
        assert not (tmp_path / "argv.txt").exists()

    def test_delivered_returns_0_with_the_cli_argv(self, tmp_path):
        fake = self._fake_python(tmp_path, rc=0)
        r = _run_function(self.REL, "notify_send", 'notify_send ops_alert "runner down: x"; echo "rc=$?"',
                          {"VENV_PY": str(fake), "PROJECT_DIR": str(tmp_path), "LOG": str(tmp_path / "log")})
        assert "rc=0" in r.stdout, r.stderr
        argv = (tmp_path / "argv.txt").read_text().splitlines()
        assert argv == ["-m", "src.notify", "send", "--kind", "ops_alert",
                        "--severity", "critical", "--text", "runner down: x"]
        # runs from the project root (the editable install is inert elsewhere)
        assert (tmp_path / "cwd.txt").read_text().strip() == str(tmp_path)

    def test_cli_failure_returns_1_so_the_caller_takes_curl(self, tmp_path):
        fake = self._fake_python(tmp_path, rc=1)
        r = _run_function(self.REL, "notify_send", 'notify_send ops_alert "x"; echo "rc=$?"',
                          {"VENV_PY": str(fake), "PROJECT_DIR": str(tmp_path), "LOG": str(tmp_path / "log")})
        assert "rc=1" in r.stdout


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
