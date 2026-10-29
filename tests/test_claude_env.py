"""
E7 — every Claude subprocess runs with error reporting + telemetry off; the
runner refuses to start with a planted vendor/auth key in its environment;
utility calls prove they were served by the requested model (spec §2.4/§3, §6
"Startup assertion over the named Anthropic credentials", §9 Phase-1 exit rows
7–8; design of record P0 plan Task 17 + the re-cut E7 Deltas: inline
`env=claude_subprocess_env()` at the five ClaudeAgentOptions sites, no builder
extraction; `utility_model_usage` via getattr in `llm_route` / `extract_learning`,
audited under job id "utility", never failing the call; `scripts/run.sh` uses
`env PIPENV_DONT_LOAD_ENV=1 pipenv run …`).

Pure — source pins, string pins, a fake SDK `query`. The startup test drives the
real `_check_subscription_auth` with a planted key.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_claude_env.py -q
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.runner.claude_env import (
    CLAUDE_SUBPROCESS_ENV,
    VENDOR_KEY_EXACT,
    VENDOR_KEY_PREFIXES,
    VENDOR_KEY_SUFFIXES,
    claude_subprocess_env,
    utility_model_violation,
    vendor_keys_in,
)

REPO = Path(__file__).resolve().parent.parent


def _clear_vendor_keys(monkeypatch):
    """VENDOR_KEY_PREFIXES holds PREFIXES, so the environment has to be
    scanned (`pipenv run` without PIPENV_DONT_LOAD_ENV exports .env)."""
    for k in vendor_keys_in(os.environ):
        monkeypatch.delenv(k, raising=False)


def test_overlay_is_exactly_the_two_keys():
    assert claude_subprocess_env() == {"DISABLE_ERROR_REPORTING": "1", "DISABLE_TELEMETRY": "1"}
    assert claude_subprocess_env() is not CLAUDE_SUBPROCESS_ENV      # a fresh copy every call


def test_vendor_keys_in_names_not_prefix():
    # spec §6: the FOUR Anthropic credential names, never a blanket ANTHROPIC_*
    # — a prefix would refuse to boot the moment a plist carries an
    # ANTHROPIC_MAX_SESSIONS-shaped knob. The spec's `*_TOKEN` glob is not
    # adopted: TELEGRAM_BOT_TOKEN / TRADIER_SANDBOX_TOKEN / FINNHUB_TOKEN are
    # legitimate Settings names that `pipenv run` would export.
    assert set(VENDOR_KEY_EXACT) == {"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                                     "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN"}
    assert set(VENDOR_KEY_PREFIXES) == {"GEMINI_", "CEREBRAS_", "GROQ_",
                                        "OPENROUTER_", "OPENAI_", "XAI_"}       # no CODEX_: see below
    assert VENDOR_KEY_SUFFIXES == ("_API_KEY",)
    assert not any(p.startswith("ANTHROPIC") for p in VENDOR_KEY_PREFIXES)
    assert vendor_keys_in({"ANTHROPIC_MAX_SESSIONS": "2", "HOME": "/x"}) == []
    assert vendor_keys_in({"TELEGRAM_BOT_TOKEN": "x", "TRADIER_SANDBOX_TOKEN": "y",
                           "FINNHUB_TOKEN": "z", "WEB_AUTH_TOKEN": "w"}) == []
    assert vendor_keys_in({"GEMINI_API_KEY": "x", "PATH": "/bin"}) == ["GEMINI_API_KEY"]
    assert vendor_keys_in({"OPENROUTER_API_KEY": "w", "CEREBRAS_KEY": "x", "GROQ_API_KEY": "y",
                           "CODEX_API_KEY": "z", "ANTHROPIC_API_KEY": "v"}) == [
        "ANTHROPIC_API_KEY", "CEREBRAS_KEY", "CODEX_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"]
    # CODEX_API_KEY is caught by the suffix; the Codex CLI's own CODEX_HOME and
    # this repo's CODEX_* Settings knobs are NOT credentials (review 2026-10-29).
    assert vendor_keys_in({"CODEX_HOME": "/x", "CODEX_BIN": "/opt/codex",
                           "CODEX_SANDBOX_DEFAULT": "workspace-write", "CODEX_RUN_AS_USER": "u"}) == []
    for name in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "OPENAI_API_KEY",
                 "XAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "TOGETHER_API_KEY"):
        assert vendor_keys_in({name: "x"}) == [name], name
    assert vendor_keys_in({"ANTHROPIC_API_KEY_HINT": ""}) == []       # neither a name nor a suffix


@pytest.mark.parametrize("name", [
    "GEMINI_API_KEY", "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN", "OPENAI_API_KEY", "XAI_API_KEY", "TOGETHER_API_KEY",
])
def test_startup_env_refuses_planted_key(monkeypatch, name):
    """§8 exit row 7: the runner refuses to start with a planted key. EVERY
    name in the set is fail-closed; none warns and continues."""
    from src.runner import main as main_mod
    _clear_vendor_keys(monkeypatch)
    monkeypatch.setenv(name, "leak")
    with pytest.raises(SystemExit):
        main_mod._check_subscription_auth()


def test_startup_passes_on_a_clean_env(monkeypatch):
    from src.runner import main as main_mod
    _clear_vendor_keys(monkeypatch)
    main_mod._check_subscription_auth()          # no SystemExit


def test_anthropic_api_key_still_reads_as_the_inv3_violation(monkeypatch, capsys):
    from src.runner import main as main_mod
    _clear_vendor_keys(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    with pytest.raises(SystemExit):
        main_mod._check_subscription_auth()
    assert "INV-3" in capsys.readouterr().err


def test_no_settings_field_name_is_in_the_refusal_set():
    # `pipenv run` exports .env as upper-cased Settings names; a launch that
    # does so must not refuse to start on a config knob. Regression pin as
    # Settings grows (review 2026-10-29: CODEX_* used to collide).
    from src.config import Settings
    names = {f.upper() for f in Settings.model_fields}
    assert vendor_keys_in({n: "x" for n in names}) == []


def test_provisioning_exempt_is_a_subset_of_vendor_keys():
    # D1's pre-check never defers on a key the runner would refuse to start
    # with anyway — the two sets must agree on the Anthropic names.
    from src.runner import main as main_mod
    assert main_mod.PROVISIONING_EXEMPT <= set(VENDOR_KEY_EXACT)


def test_five_option_sites_carry_the_overlay():
    # Source pins for the five inline ClaudeAgentOptions(...) sites: the
    # session, the router, the learning extractor, the reviewer, the judge.
    import evals.run as evals_run
    from src.runner import learning, llm_router, review, session
    assert '**claude_subprocess_env()}' in inspect.getsource(session._build_options)   # merged, never clobbering
    for mod in (llm_router, learning, review, evals_run):
        src = inspect.getsource(mod)
        assert "env=claude_subprocess_env()" in src, mod.__name__
        # every construction in the module carries it (one site per module today)
        assert src.count("ClaudeAgentOptions(\n") == src.count("env=claude_subprocess_env()"), mod.__name__


def test_run_sh_uses_env_prefix():
    # `pipenv run` copies .env into os.environ; a vendor key in .env would
    # then trip the startup refusal. `_start_one` execs its arguments, so a
    # bare VAR=value would be run as a command — it has to go through `env`.
    src = (REPO / "scripts/run.sh").read_text()
    for svc in ("runner", "web", "bot"):
        line = next(l for l in src.splitlines() if f"_start_one {svc} " in l)
        assert f"_start_one {svc} env PIPENV_DONT_LOAD_ENV=1 pipenv run" in line, line


def test_installer_services_carry_telemetry_off():
    src = (REPO / "scripts/install-launchd.sh").read_text()
    # The services template sits between its PATH key and its RunAtLoad key.
    services = src.split("<key>PATH</key>", 1)[1].split("<key>RunAtLoad</key>", 1)[0]
    assert "<key>DISABLE_ERROR_REPORTING</key><string>1</string>" in services
    assert "<key>DISABLE_TELEMETRY</key><string>1</string>" in services


def test_installer_never_exports_credentials():
    # §8 exit row 7's live check (`plutil … | grep -c CLAUDE_CODE_OAUTH_TOKEN`
    # → 0) at the source: no plist the installer writes can carry one.
    src = (REPO / "scripts/install-launchd.sh").read_text()
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY=", "GEMINI_API_KEY",
                 "TELEGRAM_BOT_TOKEN", "setup-token", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
        assert name not in src, name


def test_utility_model_violation_reports_extra_families_only():
    assert utility_model_violation({"claude-sonnet-4-6": {}}, "claude-sonnet-4-6") == []
    assert utility_model_violation(
        {"claude-sonnet-4-6": {}, "claude-haiku-4-5-20251001": {}},
        "claude-sonnet-4-6") == ["claude-haiku-4-5-20251001"]
    assert utility_model_violation({}, "claude-sonnet-4-6") == []      # absent ≠ wrong
    assert utility_model_violation(None, "claude-sonnet-4-6") == []


def _result_message(model_usage):
    from claude_agent_sdk import ResultMessage
    return ResultMessage(subtype="success", duration_ms=10, duration_api_ms=5, is_error=False,
                         num_turns=1, session_id="s", structured_output={"skill": "", "confidence": 0.1},
                         model_usage=model_usage)


def _fake_query(message):
    async def fake(prompt: str, options):  # noqa: ANN001 — mirrors the SDK signature
        yield message
    return fake


class TestUtilityModelUsageIsAudited:
    """§8 exit row 8: `model_usage` on utility calls lists only the requested
    model — checked on every router and learning call; a second family is
    logged + audited (`utility_model_usage{call, requested, served_models}`
    under job id "utility"), never a failure."""

    @pytest.fixture
    def audited(self, monkeypatch):
        rows: list[tuple] = []
        monkeypatch.setattr("src.audit_log.append",
                            lambda job_id, kind, **f: rows.append((job_id, kind, f)))
        return rows

    async def test_router_audits_a_second_family(self, monkeypatch, audited, caplog):
        import logging
        from src.runner import llm_router
        monkeypatch.setattr(llm_router.settings, "llm_router_enabled", True)
        monkeypatch.setattr(llm_router.settings, "utility_model", "claude-sonnet-4-6")
        monkeypatch.setattr("src.registry.skills.list_all",
                            lambda *a, **k: [SimpleNamespace(name="idea-generation", description="x")])
        msg = _result_message({"claude-sonnet-4-6": {"inputTokens": 1},
                               "claude-haiku-4-5-20251001": {"inputTokens": 1}})
        monkeypatch.setattr(llm_router, "query", _fake_query(msg))
        with caplog.at_level(logging.WARNING):
            out = await llm_router.llm_route("do something ambiguous")
        assert isinstance(out, tuple)                                  # the call's outcome is untouched
        rows = [r for r in audited if r[1] == "utility_model_usage"]
        assert len(rows) == 1
        job_id, _, f = rows[0]
        assert job_id == "utility" and f["call"] == "router"
        assert f["requested"] == "claude-sonnet-4-6"
        assert f["served_models"] == ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"]
        assert "utility_model_usage" in caplog.text

    async def test_router_is_silent_when_only_the_requested_model_served(self, monkeypatch, audited):
        from src.runner import llm_router
        monkeypatch.setattr(llm_router.settings, "llm_router_enabled", True)
        monkeypatch.setattr(llm_router.settings, "utility_model", "claude-sonnet-4-6")
        monkeypatch.setattr("src.registry.skills.list_all",
                            lambda *a, **k: [SimpleNamespace(name="idea-generation", description="x")])
        monkeypatch.setattr(llm_router, "query",
                            _fake_query(_result_message({"claude-sonnet-4-6": {"inputTokens": 1}})))
        await llm_router.llm_route("do something ambiguous")
        assert [r for r in audited if r[1] == "utility_model_usage"] == []

    async def test_learning_audits_a_second_family(self, monkeypatch, audited):
        from src.runner import learning
        monkeypatch.setattr(learning.settings, "utility_model", "claude-sonnet-4-6")
        msg = _result_message({"claude-sonnet-4-6": {}, "claude-haiku-4-5-20251001": {}})
        msg.structured_output = {"had_learning": False}
        monkeypatch.setattr(learning, "query", _fake_query(msg))
        out = await learning.extract_learning("job12345", [], "summary", ["runner"])
        assert out.had_learning is False
        rows = [r for r in audited if r[1] == "utility_model_usage"]
        assert len(rows) == 1 and rows[0][2]["call"] == "learning" and rows[0][0] == "utility"

    def test_audit_docstring_lists_the_kind(self):
        doc = (REPO / "src" / "audit_log.py").read_text(encoding="utf-8")
        assert "- utility_model_usage:" in doc
