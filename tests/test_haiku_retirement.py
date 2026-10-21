"""
T0 — Haiku 4.5 retirement (cross-vendor writer slice, 2026-10-21).

Guards that the retired `claude-haiku-4-5-20251001` id is gone from every
place the server could still serve it, and that the two fail-open utility
classifiers (LLM router, learning extractor) run on `settings.utility_model`
at `settings.utility_effort` instead of a hard-coded pin.

Pure/fixture style: the SDK `query` entry points are monkeypatched with a
fake that records the options it was handed — no network, no live SDK.

Run: pipenv run pytest tests/test_haiku_retirement.py -v
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.config import Settings, settings
from src.gateway import telegram_bot
from src.runner import learning, llm_router, session

REPO = Path(__file__).resolve().parent.parent
RETIRED_ID = "claude-haiku-4-5-20251001"


# ── 1. The literal is gone ─────────────────────────────────────────────────


def _files_mentioning_retired_id(paths: list[Path]) -> list[str]:
    return sorted(
        str(p.relative_to(REPO))
        for p in paths
        if p.is_file() and RETIRED_ID in p.read_text(encoding="utf-8", errors="replace")
    )


def test_no_retired_haiku_literal_under_src():
    hits = _files_mentioning_retired_id(list((REPO / "src").rglob("*.py")))
    assert hits == [], f"retired model id still served from: {hits}"


def test_no_retired_haiku_literal_in_skill_frontmatter_or_skill_docs():
    paths = list((REPO / "skills").glob("*/SKILL.md"))
    paths += [REPO / "skills" / "README.md", REPO / "skills" / "TEMPLATE.md"]
    hits = _files_mentioning_retired_id(paths)
    assert hits == [], f"retired model id still referenced by: {hits}"


# ── 2. Settings carry the utility model ───────────────────────────────────


def test_settings_utility_model_defaults():
    # Field defaults, not the loaded instance — the dev .env may override.
    assert Settings.model_fields["utility_model"].default == "claude-sonnet-4-6"
    assert Settings.model_fields["utility_effort"].default == "low"


# ── 3. The two fail-open classifiers read the setting ─────────────────────


class _Captured:
    options = None


def _fake_query(captured: _Captured):
    async def fake(prompt: str, options):  # noqa: ANN001 — mirrors SDK signature
        captured.options = options
        if False:  # pragma: no cover — makes this an async generator
            yield None

    return fake


def _fake_catalog(monkeypatch) -> None:
    # `llm_route` imports `list_all` late from the registry module, so patch
    # it there: the catalog build must not touch `settings.skills_dir`
    # (the prod tree from the dev checkout) — a missing/unreadable dir would
    # short-circuit to ("", 0.0) before `query` is ever called.
    monkeypatch.setattr(
        "src.registry.skills.list_all",
        lambda *a, **k: [SimpleNamespace(name="idea-generation", description="x")],
    )


def test_llm_route_uses_settings_utility_model(monkeypatch):
    captured = _Captured()
    _fake_catalog(monkeypatch)
    monkeypatch.setattr(llm_router, "query", _fake_query(captured))
    monkeypatch.setattr(settings, "llm_router_enabled", True)
    monkeypatch.setattr(settings, "utility_model", "claude-sonnet-4-6")
    monkeypatch.setattr(settings, "utility_effort", "low")

    result = asyncio.run(llm_router.llm_route("do something ambiguous"))

    assert result == ("", 0.0)  # fake yields nothing → generic task
    assert captured.options is not None, "query was never called"
    assert captured.options.model == settings.utility_model
    assert captured.options.effort == settings.utility_effort
    assert captured.options.model != RETIRED_ID


def test_llm_route_follows_setting_override(monkeypatch):
    captured = _Captured()
    _fake_catalog(monkeypatch)
    monkeypatch.setattr(llm_router, "query", _fake_query(captured))
    monkeypatch.setattr(settings, "llm_router_enabled", True)
    monkeypatch.setattr(settings, "utility_model", "claude-opus-4-7")
    monkeypatch.setattr(settings, "utility_effort", "medium")

    asyncio.run(llm_router.llm_route("do something ambiguous"))

    assert captured.options.model == "claude-opus-4-7"
    assert captured.options.effort == "medium"


def test_extract_learning_uses_settings_utility_model(monkeypatch):
    captured = _Captured()
    monkeypatch.setattr(learning, "query", _fake_query(captured))
    monkeypatch.setattr(settings, "utility_model", "claude-sonnet-4-6")
    monkeypatch.setattr(settings, "utility_effort", "low")

    proposal = asyncio.run(
        learning.extract_learning("job-1234", [], "did the thing", ["runner"])
    )

    assert proposal.had_learning is False  # fake yields nothing → no learning
    assert captured.options is not None, "query was never called"
    assert captured.options.model == settings.utility_model
    assert captured.options.effort == settings.utility_effort
    assert captured.options.model != RETIRED_ID


def test_extract_learning_follows_setting_override(monkeypatch):
    captured = _Captured()
    monkeypatch.setattr(learning, "query", _fake_query(captured))
    monkeypatch.setattr(settings, "utility_model", "claude-opus-4-7")
    monkeypatch.setattr(settings, "utility_effort", "medium")

    asyncio.run(learning.extract_learning("job-1234", [], "summary", ["runner"]))

    assert captured.options.model == "claude-opus-4-7"
    assert captured.options.effort == "medium"


# ── 4. Gateway alias table and dashboard ──────────────────────────────────


def test_alias_table_has_no_haiku_key_or_value():
    assert not any("haiku" in k for k in telegram_bot._MODEL_ALIASES)
    assert not any("haiku" in v for v in telegram_bot._MODEL_ALIASES.values())


def test_retired_haiku_alias_resolves_to_sonnet():
    # `--model=haiku` typed from muscle memory must not leak a retired or
    # bare id into job.payload — it lands on the utility replacement.
    assert telegram_bot.parse_flags("--model=haiku x")[1]["model"] == "claude-sonnet-4-6"
    assert telegram_bot.parse_flags("--model=haiku-4-5 x")[1]["model"] == "claude-sonnet-4-6"


def test_dashboard_model_select_has_no_haiku_option():
    from src.gateway import web

    html = Path(web.__file__).read_text(encoding="utf-8")
    assert "haiku" not in html.lower()


# ── 5. Budget table ───────────────────────────────────────────────────────


def test_model_budgets_have_no_haiku_row_and_cover_utility_model():
    assert not any("haiku" in k for k in session._MODEL_BUDGETS)
    assert Settings.model_fields["utility_model"].default in session._MODEL_BUDGETS
