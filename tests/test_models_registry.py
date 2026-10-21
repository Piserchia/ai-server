"""
T1 — Models registry and provider-qualified ids (cross-vendor writer slice,
2026-10-21; plan §5 T1, old spec §2.5).

`models.yml` at the repo root is the one list of providers, model ids,
aliases and context windows. `src/registry/models.py` parses
`[provider/]model_id` (bare → `anthropic/`), resolves aliases, and refuses
anything it does not know with `ProviderRefused` — C12: fail closed, never
a default. The gateway alias table, the dashboard dropdown, the session
budget table and the skill-contract allowlist are all derived from it, and
the two paths T0's review found unvalidated (`POST /api/jobs` and
`job.payload["model"]` in the session) now go through it.

Pure/fixture style: no network, no SDK, no DB. The web positive case fakes
`enqueue_job`; the registry-from-yml cases write a throwaway yml.

Run: pipenv run pytest tests/test_models_registry.py -v
"""

from __future__ import annotations

import ast
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient

from src.config import Settings, settings
from src.registry import models as reg
from src.registry.skills import SkillConfig, list_all

REPO = Path(__file__).resolve().parent.parent
REPO_SKILLS = REPO / "skills"

RETIRED_ID = "claude-haiku-4-5-20251001"

# The allowlist as it stood before T1 (`set(telegram_bot._MODEL_ALIASES.values())`
# after T0) — the registry must reproduce it exactly, plus the codex ids.
TODAYS_ANTHROPIC_IDS = {
    "claude-opus-4-7", "claude-opus-5", "claude-opus-4-8", "claude-opus-4-6",
    "claude-fable-5", "claude-sonnet-4-6",
}
CODEX_IDS = {"gpt-6-luna", "gpt-6-sol", "gpt-6-astra"}

# The gateway alias table exactly as T0 left it (keys and values).
PRE_T1_ALIASES = {
    "opus": "claude-opus-4-7",
    "opus-5": "claude-opus-5",
    "opus-4-8": "claude-opus-4-8",
    "opus-4-7": "claude-opus-4-7",
    "opus-4-6": "claude-opus-4-6",
    "fable": "claude-fable-5",
    "fable-5": "claude-fable-5",
    "sonnet": "claude-sonnet-4-6",
    "sonnet-4-6": "claude-sonnet-4-6",
}


# ── 1. Parse table ────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,expected", [
    ("claude-opus-4-7", ("anthropic", "claude-opus-4-7")),          # bare → anthropic/
    ("anthropic/claude-opus-4-7", ("anthropic", "claude-opus-4-7")),
    ("codex/gpt-6-luna", ("codex", "gpt-6-luna")),
    ("Codex/GPT-6-Luna", ("codex", "gpt-6-luna")),                   # case-folded
    ("  codex/gpt-6-sol  ", ("codex", "gpt-6-sol")),                 # stripped
    ("", ("", "")),                                                  # "" = no pin
    ("gpt-6-luna", ("anthropic", "gpt-6-luna")),                     # bare codex id is NOT codex
])
def test_split_model_ref(raw, expected):
    assert reg.split_model_ref(raw) == expected


def test_split_model_ref_is_total_on_malformed_id():
    # The split never raises (SkillConfig.provider must not blow up on load);
    # the extra slash lands in model_id and resolve() refuses it.
    assert reg.split_model_ref("a/b/c") == ("a", "b/c")
    with pytest.raises(reg.ProviderRefused):
        reg.resolve("anthropic/claude-opus-4-7/extra")


# ── 2. Resolution + aliases ───────────────────────────────────────────────


def test_resolve_bare_anthropic_id():
    ref = reg.resolve("claude-opus-4-7")
    assert ref == reg.ModelRef("anthropic", "claude-opus-4-7")
    assert ref.qualified == "anthropic/claude-opus-4-7"
    assert ref.canonical == "claude-opus-4-7"   # Anthropic stays bare in payloads


def test_resolve_qualified_anthropic_id_is_same_ref():
    assert reg.resolve("anthropic/claude-opus-4-7") == reg.resolve("claude-opus-4-7")


def test_resolve_codex_id():
    ref = reg.resolve("codex/gpt-6-luna")
    assert ref.provider == "codex" and ref.model_id == "gpt-6-luna"
    assert ref.canonical == "codex/gpt-6-luna"   # non-Anthropic stays qualified


@pytest.mark.parametrize("alias,target", sorted(PRE_T1_ALIASES.items()))
def test_resolve_every_pre_t1_alias(alias, target):
    assert reg.resolve(alias).canonical == target
    assert reg.resolve(f"anthropic/{alias}").canonical == target


def test_resolve_is_idempotent_on_canonical():
    for raw in ("opus", "codex/gpt-6-sol", "anthropic/sonnet"):
        canon = reg.resolve(raw).canonical
        assert reg.resolve(canon).canonical == canon


# ── 3. Fail closed ────────────────────────────────────────────────────────


@pytest.mark.parametrize("raw,reason_fragment", [
    ("openai/gpt-6-luna", "unknown provider"),
    ("gemini/flash", "unknown provider"),
    ("codex/claude-opus-4-7", "unknown model"),
    ("anthropic/gpt-6-luna", "unknown model"),
    ("gpt-6-luna", "unknown model"),              # bare → anthropic/, C12: never a default
    (RETIRED_ID, "unknown model"),                # retired id is gone from the registry
    ("claude-opus-9", "unknown model"),
    ("", "empty"),
    ("   ", "empty"),
])
def test_resolve_refuses(raw, reason_fragment):
    with pytest.raises(reg.ProviderRefused) as ei:
        reg.resolve(raw)
    assert reason_fragment in ei.value.reason
    assert ei.value.raw == raw
    assert reason_fragment in str(ei.value)


def test_provider_refused_is_a_value_error_with_fields():
    exc = reg.ProviderRefused("x/y", "unknown provider", provider="x", model_id="y")
    assert isinstance(exc, ValueError)
    assert (exc.raw, exc.reason, exc.provider, exc.model_id) == ("x/y", "unknown provider", "x", "y")


# ── 4. Every skill frontmatter and escalation target resolves ────────────


ALL_SKILLS = list_all(REPO_SKILLS)


def test_skill_corpus_is_the_expected_size():
    # Guards the two parametrized tests below against a vacuous pass.
    assert len(ALL_SKILLS) >= 72
    targets = [s for s in ALL_SKILLS if (s.escalation or {}).get("on_failure", {}).get("model")]
    assert len(targets) >= 31


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=[s.name for s in ALL_SKILLS])
def test_every_frontmatter_model_resolves(skill: SkillConfig):
    if skill.model == "":
        return   # "" = settings.default_model, resolved at job time
    ref = reg.resolve(skill.model)
    assert ref.model_id in reg.VALID_MODELS
    assert ref.provider == skill.provider
    assert ref.model_id == skill.model_id


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=[s.name for s in ALL_SKILLS])
def test_every_escalation_target_resolves(skill: SkillConfig):
    model = (skill.escalation or {}).get("on_failure", {}).get("model")
    if model is None:
        return
    assert reg.resolve(model).model_id in reg.VALID_MODELS


def test_settings_default_model_resolves():
    assert reg.resolve(Settings.model_fields["default_model"].default).provider == "anthropic"
    assert reg.resolve(Settings.model_fields["utility_model"].default).provider == "anthropic"


# ── 5. Derived tables equal today's ───────────────────────────────────────


def test_valid_models_is_todays_set_plus_codex_ids():
    assert reg.VALID_MODELS == TODAYS_ANTHROPIC_IDS | CODEX_IDS
    assert isinstance(reg.VALID_MODELS, frozenset)
    assert RETIRED_ID not in reg.VALID_MODELS


def test_alias_table_equals_pre_t1_gateway_table():
    assert reg.alias_table() == PRE_T1_ALIASES


def test_gateway_alias_table_is_fed_from_registry():
    from src.gateway import telegram_bot

    assert telegram_bot._MODEL_ALIASES == reg.alias_table()
    # T0's behaviour is preserved end to end.
    assert telegram_bot.parse_flags("--model=opus x")[1]["model"] == "claude-opus-4-7"
    assert telegram_bot.parse_flags("--model=fable-5 x")[1]["model"] == "claude-fable-5"
    assert telegram_bot.parse_flags("--model=haiku x")[1]["model"] == "claude-sonnet-4-6"
    # A qualified id passes through untouched for the registry to validate downstream.
    assert telegram_bot.parse_flags("--model=codex/gpt-6-luna x")[1]["model"] == "codex/gpt-6-luna"


def test_context_windows_feed_session_budgets():
    from src.runner import session

    windows = reg.context_windows()
    assert windows["claude-sonnet-4-6"] == 200_000
    assert windows["claude-opus-4-7"] == 200_000
    assert windows["gpt-6-luna"] == 1_050_000       # chatgpt-openai.md §1
    assert set(windows) == reg.VALID_MODELS
    assert session._MODEL_BUDGETS == windows
    # test_context_budget's contract: known model → its window, unknown → 200k default.
    assert session.context_budget_fraction("x" * 800, "claude-sonnet-4-6")[1] == 200_000
    assert session.context_budget_fraction("x" * 800, "nope")[1] == 200_000


def test_list_models_orders_by_provider_then_yml_order():
    allm = reg.list_models()
    assert [m.provider for m in allm] == ["anthropic"] * 6 + ["codex"] * 3
    assert allm[0].model_id == "claude-sonnet-4-6"       # dashboard's first option, as today
    assert allm[1].model_id == "claude-opus-4-7"
    assert [m.model_id for m in reg.list_models("codex")] == ["gpt-6-luna", "gpt-6-sol", "gpt-6-astra"]
    assert reg.list_models("nope") == []
    assert all(m.label for m in allm)


def test_providers_lists_both():
    assert reg.providers() == ("anthropic", "codex")


# ── 6. Registry loading from yml (shape rules) ───────────────────────────


def _write_yml(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "models.yml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def test_registry_loads_from_explicit_path_and_qualifies_non_anthropic_aliases(tmp_path):
    p = _write_yml(tmp_path, {"providers": {
        "anthropic": {"executor": "sdk-anthropic", "models": {
            "claude-sonnet-4-6": {"label": "s", "context_window": 1, "aliases": ["sonnet"]}}},
        "codex": {"executor": "codex_cli", "models": {
            "gpt-6-luna": {"label": "l", "context_window": 2, "aliases": ["luna"]}}},
    }})
    r = reg.Registry.load(p)
    assert r.valid_models == {"claude-sonnet-4-6", "gpt-6-luna"}
    # Non-Anthropic aliases are only honoured qualified (bare → anthropic/, C12) …
    assert r.resolve("codex/luna").canonical == "codex/gpt-6-luna"
    with pytest.raises(reg.ProviderRefused):
        r.resolve("luna")
    # … and the flat alias table keys them the same way, so parse_flags and
    # resolve() can never disagree.
    assert r.alias_table() == {"sonnet": "claude-sonnet-4-6", "codex/luna": "codex/gpt-6-luna"}


def test_registry_missing_file_raises():
    with pytest.raises(reg.RegistryError):
        reg.Registry.load(Path("/nonexistent/models.yml"))


@pytest.mark.parametrize("bad", [
    {},                                                        # no providers
    {"providers": []},                                         # wrong type
    {"providers": {"anthropic": {"models": {}}}},               # no models
    {"providers": {"anthropic": {"models": {"m": {"context_window": "big"}}}}},  # non-int window
    {"providers": {"anthropic": {"models": {"m": {"aliases": "m2"}}}}},         # aliases not a list
    {"providers": {"Anthropic": {"models": {"m": {}}}}},        # provider names are lowercase
    {"providers": {"anthropic": {"models": {"a/b": {}}}}},      # model ids carry no slash
])
def test_registry_rejects_bad_shapes(tmp_path, bad):
    with pytest.raises(reg.RegistryError):
        reg.Registry.load(_write_yml(tmp_path, bad))


def test_registry_rejects_alias_collisions(tmp_path):
    # Same alias twice in one provider, or an alias that shadows a model id.
    with pytest.raises(reg.RegistryError):
        reg.Registry.load(_write_yml(tmp_path, {"providers": {"anthropic": {"models": {
            "a": {"aliases": ["x"]}, "b": {"aliases": ["x"]}}}}}))
    with pytest.raises(reg.RegistryError):
        reg.Registry.load(_write_yml(tmp_path, {"providers": {"anthropic": {"models": {
            "a": {"aliases": ["b"]}, "b": {}}}}}))


def test_default_registry_file_is_at_repo_root():
    assert reg.DEFAULT_PATH == REPO / "models.yml"
    assert reg.DEFAULT_PATH.exists()


# ── 7. Settings ───────────────────────────────────────────────────────────


def test_settings_provider_fields_default_fail_closed():
    f = Settings.model_fields
    assert f["router_providers_enabled"].default == "anthropic"
    assert f["router_code_server_providers"].default == "anthropic"
    assert f["codex_bin"].default == ""
    assert f["codex_home"].default == ""
    assert f["codex_sandbox_default"].default == "workspace-write"


def test_enabled_providers_parses_csv(monkeypatch):
    monkeypatch.setattr(settings, "router_providers_enabled", " Anthropic , codex,,")
    assert reg.enabled_providers() == frozenset({"anthropic", "codex"})
    monkeypatch.setattr(settings, "router_providers_enabled", "")
    assert reg.enabled_providers() == frozenset()


def test_resolve_enabled_refuses_disabled_provider(monkeypatch):
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
    assert reg.resolve_enabled("opus").canonical == "claude-opus-4-7"
    with pytest.raises(reg.ProviderRefused) as ei:
        reg.resolve_enabled("codex/gpt-6-luna")
    assert "not enabled" in ei.value.reason and ei.value.provider == "codex"
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
    assert reg.resolve_enabled("codex/gpt-6-luna").provider == "codex"


# ── 8. SkillConfig derives provider / model_id; `model` stays raw ─────────


def test_skill_config_derived_fields():
    cfg = SkillConfig(name="x", body="b", model="codex/gpt-6-luna")
    assert cfg.model == "codex/gpt-6-luna"          # raw string, untouched
    assert (cfg.provider, cfg.model_id) == ("codex", "gpt-6-luna")

    bare = SkillConfig(name="x", body="b", model="claude-opus-4-7")
    assert (bare.provider, bare.model_id) == ("anthropic", "claude-opus-4-7")

    unpinned = SkillConfig(name="x", body="b")
    assert unpinned.model == ""
    assert (unpinned.provider, unpinned.model_id) == ("", "")


def test_skill_config_derivation_does_not_validate():
    # Loading never fails on an unknown provider — the JOB fails (C12), so
    # list_all() for SKILLS_REGISTRY.md keeps working on a bad frontmatter.
    cfg = SkillConfig(name="x", body="b", model="nope/whatever")
    assert (cfg.provider, cfg.model_id) == ("nope", "whatever")
    malformed = SkillConfig(name="y", body="b", model="a/b/c")
    assert (malformed.provider, malformed.model_id) == ("a", "b/c")   # no raise on load


# ── 9. Session: payload / skill / default precedence, fail closed ─────────


def _skill(model: str = "") -> SkillConfig:
    return SkillConfig(name="demo", body="Do it.", model=model)


def test_session_resolve_model_precedence(monkeypatch):
    from src.runner import session

    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
    monkeypatch.setattr(settings, "default_model", "claude-sonnet-4-6")
    # payload > skill > default
    assert session._resolve_model({"model": "opus"}, _skill("claude-opus-5")).canonical == "claude-opus-4-7"
    assert session._resolve_model({}, _skill("claude-opus-5")).canonical == "claude-opus-5"
    assert session._resolve_model({"model": ""}, _skill("claude-opus-5")).canonical == "claude-opus-5"
    assert session._resolve_model({}, _skill()).canonical == "claude-sonnet-4-6"
    assert session._resolve_model(None, None).canonical == "claude-sonnet-4-6"
    # Qualified Anthropic ids hand the SDK the same bare id as today.
    assert session._resolve_model({"model": "anthropic/sonnet"}, None).model_id == "claude-sonnet-4-6"


def test_session_refuses_retired_payload_model(monkeypatch):
    # The T0-review hole: a stale client (or an old schedule payload) naming
    # the retired Haiku id reached the SDK unvalidated.
    from src.runner import session

    with pytest.raises(reg.ProviderRefused) as ei:
        session._resolve_model({"model": RETIRED_ID}, None)
    assert "unknown model" in ei.value.reason


def test_session_refuses_unknown_skill_pin(monkeypatch):
    from src.runner import session

    with pytest.raises(reg.ProviderRefused):
        session._resolve_model({}, _skill("openai/gpt-6-luna"))


def test_session_refuses_disabled_provider_by_default(monkeypatch):
    from src.runner import session

    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
    with pytest.raises(reg.ProviderRefused) as ei:
        session._resolve_model({"model": "codex/gpt-6-luna"}, None)
    assert "not enabled" in ei.value.reason


def test_session_refuses_enabled_provider_without_executor(monkeypatch):
    # Interim until T4 lands the dispatch branch: an enabled non-Anthropic
    # provider still cannot reach the Anthropic SDK with a foreign model id.
    from src.runner import session

    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic,codex")
    with pytest.raises(reg.ProviderRefused) as ei:
        session._resolve_model({"model": "codex/gpt-6-luna"}, None)
    assert "no executor" in ei.value.reason


def test_session_refuses_unknown_default_model(monkeypatch):
    from src.runner import session

    monkeypatch.setattr(settings, "default_model", "claude-haiku-4-5-20251001")
    with pytest.raises(reg.ProviderRefused):
        session._resolve_model({}, None)


# ── 10. Runner main: ProviderRefused is terminal, audited, not escalated ──


def _handler_type_name(node: ast.ExceptHandler) -> str:
    t = node.type
    if isinstance(t, ast.Attribute):
        return t.attr
    if isinstance(t, ast.Name):
        return t.id
    return ""


def _process_job_handlers() -> list[ast.ExceptHandler]:
    """The handler list, in dispatch order, of the `try` inside `_process_job`
    that catches `ProviderRefused` (the job-outcome try; nested helper trys
    are ignored)."""
    main = REPO / "src" / "runner" / "main.py"
    tree = ast.parse(main.read_text())
    process_job = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "_process_job"
    )
    for node in ast.walk(process_job):
        if isinstance(node, ast.Try) and any(
            _handler_type_name(h) == "ProviderRefused" for h in node.handlers
        ):
            return list(node.handlers)
    raise AssertionError("_process_job has no ProviderRefused handler")


def _provider_refused_handler() -> ast.ExceptHandler:
    return next(h for h in _process_job_handlers()
                if _handler_type_name(h) == "ProviderRefused")


def test_main_handles_provider_refused_terminally():
    src = ast.unparse(_provider_refused_handler())
    assert "_finish_job" in src
    assert "JobStatus.failed" in src
    assert "'provider_refused'" in src or '"provider_refused"' in src   # audit kind + error_category
    assert "_maybe_escalate" not in src   # a policy refusal is never retried on a bigger model


def test_main_provider_refused_handler_precedes_generic_except():
    names = [_handler_type_name(h) for h in _process_job_handlers()]
    assert "ProviderRefused" in names and "Exception" in names
    assert names.index("ProviderRefused") < names.index("Exception")


# ── 11. Web: POST /api/jobs validates the model; dropdown from the registry ──


@pytest.fixture()
def client():
    from src.gateway import web

    web.app.dependency_overrides[web._check_auth] = lambda: None
    try:
        yield TestClient(web.app)
    finally:
        web.app.dependency_overrides.pop(web._check_auth, None)


def test_web_post_retired_model_is_4xx(client):
    r = client.post("/api/jobs", json={"description": "x", "model": RETIRED_ID})
    assert 400 <= r.status_code < 500
    assert "unknown model" in r.json()["detail"]


def test_web_post_unknown_provider_is_4xx(client):
    r = client.post("/api/jobs", json={"description": "x", "model": "openai/gpt-6-luna"})
    assert r.status_code == 422
    assert "unknown provider" in r.json()["detail"]


def test_web_post_disabled_provider_is_4xx(client, monkeypatch):
    monkeypatch.setattr(settings, "router_providers_enabled", "anthropic")
    r = client.post("/api/jobs", json={"description": "x", "model": "codex/gpt-6-luna"})
    assert r.status_code == 422
    assert "not enabled" in r.json()["detail"]


def test_web_post_valid_alias_is_canonicalised_into_payload(client, monkeypatch):
    from src.gateway import web

    captured: dict = {}

    async def fake_enqueue(description, **kw):
        captured.update(kw, description=description)
        return SimpleNamespace(
            id=uuid.uuid4(), kind="task", description=description, status="queued",
            resolved_skill=None, resolved_model=None, resolved_effort=None,
            user_rating=None, review_outcome=None,
            created_at=datetime.now(timezone.utc), started_at=None, completed_at=None,
            result=None, error_message=None, created_by="web",
        )

    monkeypatch.setattr(web, "enqueue_job", fake_enqueue)
    r = client.post("/api/jobs", json={"description": "x", "model": "opus"})
    assert r.status_code == 200
    assert captured["payload"] == {"model": "claude-opus-4-7"}


def test_web_post_without_model_is_unchanged(client, monkeypatch):
    from src.gateway import web

    captured: dict = {}

    async def fake_enqueue(description, **kw):
        captured.update(kw)
        return SimpleNamespace(
            id=uuid.uuid4(), kind="task", description=description, status="queued",
            resolved_skill=None, resolved_model=None, resolved_effort=None,
            user_rating=None, review_outcome=None,
            created_at=datetime.now(timezone.utc), started_at=None, completed_at=None,
            result=None, error_message=None, created_by="web",
        )

    monkeypatch.setattr(web, "enqueue_job", fake_enqueue)
    r = client.post("/api/jobs", json={"description": "x"})
    assert r.status_code == 200
    assert captured["payload"] is None


def test_web_dropdown_is_rendered_from_registry():
    from src.gateway import web

    html = web._model_options_html(enabled=frozenset({"anthropic"}))
    assert html.startswith('<option value="">default</option>')
    assert '<option value="claude-sonnet-4-6">sonnet 4.6</option>' in html
    assert '<option value="claude-opus-4-7">opus 4.7</option>' in html
    assert "codex/" not in html and "haiku" not in html
    # The served page carries the rendered options (default: anthropic only).
    assert '<option value="claude-sonnet-4-6">' in web._INDEX_HTML
    assert "{{MODEL_OPTIONS}}" not in web._INDEX_HTML


def test_web_dropdown_lists_enabled_non_anthropic_providers_qualified():
    from src.gateway import web

    html = web._model_options_html(enabled=frozenset({"anthropic", "codex"}))
    assert '<option value="codex/gpt-6-luna">' in html
    assert html.index('value="claude-sonnet-4-6"') < html.index('value="codex/gpt-6-luna"')
