"""
E10 — the daily credential canary through the runner's own SDK path (spec §0a
last rows, §6 "Credential canaries", §9 Phase-1 row; design of record P0 plan
Task 12, renamed `credential_canary` and made self-contained — the re-cut E10
Deltas; D-P1-9: `statusLine` is the one allowed extra key in user scope).

The ping goes through the SDK in the runner venv (its bundled CLI, the Keychain
login) with options built the way the runner builds them (server-root cwd, plan
mode, no tools, one turn, `setting_sources=["project"]`, E7's env overlay) and
is judged by the runner's own `served_model_violation` rule, tightened for a
probe. Before pinging it clears BOTH settings scopes — the server root (E1's
`settings_override`) and `~/.claude/settings*.json` (stricter: no tracked-file
allowance, `statusLine` the only allowed extra key) — because a user-scope
`apiKeyHelper` or `env.ANTHROPIC_BASE_URL` would make a green ping meaningless.
A pass also requires the process env WITHOUT `CLAUDE_CODE_OAUTH_TOKEN`: a pass
proves the Keychain login.

Pure: a fake `query` yielding the SDK's own dataclasses; no subprocess, no
network, no DB. `test_the_real_user_scope_is_clean_today` reads the owner's
real ~/.claude and is skipped off the Mini.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_credential_canary.py -q
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from src.runner import credential_canary as canary
from src.runner.credential_canary import (
    PING_PROMPT,
    USER_SETTINGS_ALLOWED_KEYS,
    canary_options,
    evaluate_ping,
    run_ping,
    settings_precheck,
    telemetry_record,
)
from src.runner.result_capture import capture_result_message

REPO = Path(__file__).resolve().parent.parent
MODEL = "claude-sonnet-4-6"


def _result(**over) -> ResultMessage:
    base = dict(subtype="success", duration_ms=900, duration_api_ms=600, is_error=False,
                num_turns=1, session_id="s", result="pong",
                usage={"input_tokens": 12, "output_tokens": 1, "cache_read_input_tokens": 0,
                       "cache_creation_input_tokens": 0},
                model_usage={MODEL: {"inputTokens": 12, "outputTokens": 1}})
    base.update(over)
    return ResultMessage(**base)


def _query_yielding(*messages):
    async def fake(prompt, options):  # noqa: ANN001 — mirrors the SDK signature
        fake.seen = (prompt, options)
        for m in messages:
            yield m
    return fake


class TestOptions:
    def test_canary_options_are_the_runners_one_shot_conventions(self, monkeypatch):
        from src.config import settings
        from src.runner.claude_env import claude_subprocess_env
        monkeypatch.setattr(settings, "server_root", Path("/srv/root"))
        o = canary_options(MODEL)
        assert o.cwd == "/srv/root" and o.model == MODEL
        assert o.permission_mode == "plan" and o.allowed_tools == [] and o.max_turns == 1
        assert o.setting_sources == ["project"]                      # exactly the runner's scope
        assert o.env == claude_subprocess_env()                      # E7's overlay, nothing more
        assert "CLAUDE_CODE_OAUTH_TOKEN" not in (o.env or {})


class TestEvaluate:
    def test_ok(self):
        ok, detail = evaluate_ping(capture_result_message(_result()), "pong", MODEL)
        assert ok and "ok" in detail and MODEL in detail

    def test_no_result_message_fails(self):
        ok, detail = evaluate_ping(None, "", MODEL)
        assert not ok and "no ResultMessage" in detail

    def test_is_error_fails(self):
        ok, detail = evaluate_ping(capture_result_message(_result(is_error=True, result="API Error: 401")),
                                   "", MODEL)
        assert not ok and "401" in detail

    def test_missing_model_usage_fails(self):
        # The runner forgives an absent model_usage on a short chat job; a
        # probe whose whole point is proving the credential served does not.
        ok, detail = evaluate_ping(capture_result_message(_result(model_usage=None)), "pong", MODEL)
        assert not ok and "model_usage" in detail

    def test_wrong_served_model_fails(self):
        ok, detail = evaluate_ping(
            capture_result_message(_result(model_usage={"claude-opus-4-7": {"inputTokens": 12}})),
            "pong", MODEL)
        assert not ok and "claude-opus-4-7" in detail

    def test_no_api_time_or_empty_usage_fails(self):
        ok, detail = evaluate_ping(capture_result_message(_result(duration_api_ms=0)), "pong", MODEL)
        assert not ok and "duration_api_ms" in detail
        ok, detail = evaluate_ping(capture_result_message(_result(
            usage={"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
                   "cache_creation_input_tokens": 0})), "pong", MODEL)
        assert not ok and "usage" in detail


class TestRunPing:
    async def test_run_ping_uses_the_canary_options_and_captures_the_result(self, monkeypatch):
        from src.config import settings
        monkeypatch.setattr(settings, "server_root", Path("/srv/root"))
        fake = _query_yielding(AssistantMessage(content=[TextBlock(text="pong")], model=MODEL), _result())
        capture, text = await run_ping(MODEL, timeout_s=5, query_fn=fake)
        assert text == "pong" and capture is not None and capture.model_served == MODEL
        prompt, options = fake.seen
        assert prompt == PING_PROMPT and options.setting_sources == ["project"]

    async def test_no_result_message_yields_none(self):
        fake = _query_yielding(AssistantMessage(content=[TextBlock(text="half")], model=MODEL))
        capture, text = await run_ping(MODEL, timeout_s=5, query_fn=fake)
        assert capture is None and text == "half"


class TestSettingsPrecheck:
    def _scopes(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        home = tmp_path / "home"
        (root / ".claude").mkdir(parents=True)
        (home / ".claude").mkdir(parents=True)
        from src.config import settings
        monkeypatch.setattr(settings, "server_root", root)
        monkeypatch.setattr(canary, "settings_scopes", lambda: (root, home))
        return root, home

    def test_clean_scopes_pass(self, monkeypatch, tmp_path):
        root, home = self._scopes(monkeypatch, tmp_path)
        (root / ".claude" / "settings.json").write_text(json.dumps({"enabledPlugins": {"x": True}}))
        (home / ".claude" / "settings.json").write_text(json.dumps(
            {"autoMode": True, "model": "opus", "enabledPlugins": {}, "tui": {}}))
        assert settings_precheck() is None

    def test_the_user_scope_set_is_the_specs(self):
        from src.runner.credential_canary import USER_SETTINGS_REFUSED_KEYS
        from src.runner.session import SETTINGS_AUTH_KEYS
        assert set(USER_SETTINGS_REFUSED_KEYS) == set(SETTINGS_AUTH_KEYS) | {"hooks", "env", "apiKeyHelper", "statusLine"}

    def test_statusline_is_the_only_allowed_user_key(self, monkeypatch, tmp_path):
        # D-P1-9: the owner's status-line feed (D8) lives in ~/.claude/settings.json;
        # `statusLine` is allowed there and NOWHERE else is widened.
        root, home = self._scopes(monkeypatch, tmp_path)
        assert USER_SETTINGS_ALLOWED_KEYS == frozenset({"statusLine"})
        (home / ".claude" / "settings.json").write_text(json.dumps(
            {"statusLine": {"type": "command", "command": "~/bin/rate-limits.sh"}}))
        assert settings_precheck() is None
        (home / ".claude" / "settings.json").write_text(json.dumps(
            {"statusLine": {"type": "command", "command": "x"},
             "hooks": {"SessionStart": [{"command": "id"}]}}))
        key, where = settings_precheck()
        assert key == "hooks" and where.endswith("home/.claude/settings.json")

    @pytest.mark.parametrize("payload,key", [
        ({"apiKeyHelper": "/bin/echo sk-ant-x"}, "apiKeyHelper"),
        ({"env": {"ANTHROPIC_BASE_URL": "https://proxy"}}, "ANTHROPIC_BASE_URL"),
        ({"env": {"CLAUDE_CODE_OAUTH_TOKEN": "x"}}, "CLAUDE_CODE_OAUTH_TOKEN"),
        ({"env": {"PATH": "/tmp/evil"}}, "env"),
        ({"hooks": {"SessionStart": [{"command": "id"}]}}, "hooks"),
        ({"ANTHROPIC_BASE_URL": "https://proxy"}, "ANTHROPIC_BASE_URL"),
    ])
    def test_user_scope_refuses_auth_hooks_env_and_apikeyhelper(self, monkeypatch, tmp_path, payload, key):
        # Spec §6 / plan E10: "any auth or `hooks` key" (+ `env`, `apiKeyHelper`).
        root, home = self._scopes(monkeypatch, tmp_path)
        (home / ".claude" / "settings.local.json").write_text(json.dumps(payload))
        found = settings_precheck()
        assert found is not None and found[0] == key and found[1].endswith("settings.local.json")

    @pytest.mark.parametrize("payload", [
        {"permissions": {"allow": ["Bash"]}},
        {"mcpServers": {"x": {}}},
        {"enableAllProjectMcpServers": True},
        {"enabledMcpjsonServers": ["x"]},
        {"autoMode": True, "model": "opus", "statusLine": {"type": "command", "command": "x"}},
    ])
    def test_user_scope_leaves_the_owners_editor_settings_alone(self, monkeypatch, tmp_path, payload):
        # Whole-branch review 2026-10-29: the fleet runs with setting_sources=
        # ["project"], so a user-scope `permissions`/`mcpServers` never reaches
        # a job; refusing it would turn the owner's "always allow" in their own
        # Claude Code into a red canary — and this check sits in the prod
        # deploy gate through test_the_real_user_scope_is_clean_today.
        root, home = self._scopes(monkeypatch, tmp_path)
        (home / ".claude" / "settings.json").write_text(json.dumps(payload))
        assert settings_precheck() is None

    def test_project_scope_uses_e1s_rule(self, monkeypatch, tmp_path):
        # The server root's own tracked `permissions` is allowed per E1; a hook is not.
        root, home = self._scopes(monkeypatch, tmp_path)
        (root / ".claude" / "settings.local.json").write_text(json.dumps({"permissions": {"allow": ["Bash"]}}))
        assert settings_precheck() is None
        (root / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": []}}))
        key, where = settings_precheck()
        assert key == "hooks" and where.endswith("root/.claude/settings.json")

    @pytest.mark.skipif(Path.home().name != "alfredbot.ai.butler",
                        reason="reads the Mini owner's real ~/.claude; off-box the shape differs")
    def test_the_real_user_scope_is_clean_today(self):
        # Verified 2026-10-29: autoMode / effortLevel / enabledPlugins /
        # inputNeededNotifEnabled / model / modelSettings / skipWorkflowUsageWarning
        # / tui — none refused. Keeps the green canary a fact, not an assumption.
        from src.runner.credential_canary import USER_SETTINGS_REFUSED_KEYS
        data = json.loads((Path.home() / ".claude" / "settings.json").read_text())
        refused = set(USER_SETTINGS_REFUSED_KEYS) - USER_SETTINGS_ALLOWED_KEYS
        assert not (set(data) & refused), sorted(set(data) & refused)
        env = data.get("env") if isinstance(data.get("env"), dict) else {}
        assert not (set(env) & set(USER_SETTINGS_REFUSED_KEYS)), sorted(env)


class TestMain:
    def _patch_clean(self, monkeypatch, tmp_path):
        monkeypatch.setattr(canary, "settings_precheck", lambda: None)
        monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
        return tmp_path / "telemetry.json"

    def test_exit_0_writes_telemetry(self, monkeypatch, tmp_path):
        tel = self._patch_clean(monkeypatch, tmp_path)
        monkeypatch.setattr(canary, "query", _query_yielding(
            AssistantMessage(content=[TextBlock(text="pong")], model=MODEL), _result()))
        assert canary.main(["--model", MODEL, "--telemetry", str(tel)]) == 0
        rec = json.loads(tel.read_text())
        assert rec["ok"] is True and rec["requested_model"] == MODEL and "checked_at" in rec

    def test_exit_1_on_a_failed_assertion(self, monkeypatch, tmp_path):
        tel = self._patch_clean(monkeypatch, tmp_path)
        monkeypatch.setattr(canary, "query", _query_yielding(_result(is_error=True, result="API Error: 401")))
        assert canary.main(["--model", MODEL, "--telemetry", str(tel)]) == 1
        assert json.loads(tel.read_text())["ok"] is False

    def test_exit_2_when_the_sdk_cannot_run(self, monkeypatch, tmp_path):
        tel = self._patch_clean(monkeypatch, tmp_path)

        async def boom(prompt, options):
            raise RuntimeError("CLI not found")
            yield  # pragma: no cover
        monkeypatch.setattr(canary, "query", boom)
        assert canary.main(["--model", MODEL, "--telemetry", str(tel)]) == 2

    def test_settings_hit_short_circuits_before_the_ping(self, monkeypatch, tmp_path):
        monkeypatch.setattr(canary, "settings_precheck", lambda: ("apiKeyHelper", "/h/.claude/settings.json"))
        called = []

        async def never(prompt, options):
            called.append(1)
            yield _result()
        monkeypatch.setattr(canary, "query", never)
        tel = tmp_path / "t.json"
        assert canary.main(["--model", MODEL, "--telemetry", str(tel)]) == 1
        assert called == [] and "settings_override:apiKeyHelper@" in json.loads(tel.read_text())["detail"]

    @pytest.mark.parametrize("name", ["ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
                                      "ANTHROPIC_API_KEY", "GEMINI_API_KEY"])
    def test_any_redirecting_or_rebilling_variable_in_the_env_fails(self, monkeypatch, tmp_path, name):
        # Whole-branch review 2026-10-29: ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL
        # redirect or re-bill the ping while model_usage still names the model,
        # so a token-only check could print `ok`. E7's refusal set is the contract.
        tel = self._patch_clean(monkeypatch, tmp_path)
        from src.runner.claude_env import vendor_keys_in
        for k in vendor_keys_in(dict(os.environ)):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.setenv(name, "x")
        monkeypatch.setattr(canary, "query", _query_yielding(_result()))
        assert canary.main(["--model", MODEL, "--telemetry", str(tel)]) == 1
        assert name in json.loads(tel.read_text())["detail"]

    def test_canary_never_reads_the_setup_token(self, monkeypatch, tmp_path):
        # A pass must prove the KEYCHAIN login: with CLAUDE_CODE_OAUTH_TOKEN in
        # the process env the ping would be served by the token, so it FAILS.
        tel = self._patch_clean(monkeypatch, tmp_path)
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "sk-ant-oat01-x")
        monkeypatch.setattr(canary, "query", _query_yielding(_result()))
        assert canary.main(["--model", MODEL, "--telemetry", str(tel)]) == 1
        assert "CLAUDE_CODE_OAUTH_TOKEN" in json.loads(tel.read_text())["detail"]
        src = (REPO / "src" / "runner" / "credential_canary.py").read_text()
        assert "setup-token" not in src.replace("never the sealed setup-token", "")
        assert "--bare" not in src                           # the CLI's OAuth-skipping mode

    def test_telemetry_record_shape(self):
        now = datetime(2026, 10, 29, 6, 50, tzinfo=timezone.utc)
        assert telemetry_record(True, "ok", MODEL, now) == {
            "ok": True, "detail": "ok", "requested_model": MODEL, "checked_at": now.isoformat()}


def test_the_timer_script_follows_the_launchd_contract():
    path = REPO / "scripts" / "credential-canary.sh"
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0
    src = path.read_text()
    assert "pipenv run" not in src and "--bare" not in src
    assert "-m src.runner.credential_canary" in src
    assert "src.notify send --kind credential_canary --severity critical" in src
    assert "api.telegram.org" in src                     # the curl fallback when notify itself is broken
    assert "unset ANTHROPIC_API_KEY" in src
    installer = (REPO / "scripts" / "install-launchd.sh").read_text()
    assert 'install_timer "credential-canary" "scripts/credential-canary.sh"' in installer
    assert "<integer>6</integer>" in installer.split('install_timer "credential-canary"')[1][:400]
    assert "<integer>50</integer>" in installer.split('install_timer "credential-canary"')[1][:400]
