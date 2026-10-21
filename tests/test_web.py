"""Dashboard / REST surfaces: provider everywhere the owner looks (cross-vendor
writer slice T7, 2026-10-21).

- `GET /api/jobs` rows carry the 007 provider columns (`resolved_provider`,
  `model_served`, `terminal_reason`) additively.
- The jobs table has a provider column.
- The model `<select>` is rendered from the registry, grouped by provider
  (`<optgroup>` per ENABLED provider, models.yml order).

Pure / TestClient only — no runner, no DB, no network.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.gateway import web
from src.registry import models as reg


@pytest.fixture()
def client():
    web.app.dependency_overrides[web._check_auth] = lambda: None
    try:
        yield TestClient(web.app)
    finally:
        web.app.dependency_overrides.pop(web._check_auth, None)


def _job(**over) -> SimpleNamespace:
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    base = dict(
        id=uuid.uuid4(), kind="task", description="fix it", status="completed",
        resolved_skill="app-patch", resolved_model="gpt-6-luna", resolved_effort="medium",
        user_rating=None, review_outcome="LGTM", created_at=now, started_at=now,
        completed_at=now, result={"summary": "ok"}, error_message=None,
        created_by="web", resolved_provider="codex", model_served="gpt-6-luna-2026-10",
        terminal_reason="ok",
    )
    base.update(over)
    return SimpleNamespace(**base)


class TestJobOutProviderFields:
    def test_serialize_carries_the_007_columns(self):
        out = web._serialize(_job()).model_dump()
        assert out["resolved_provider"] == "codex"
        assert out["model_served"] == "gpt-6-luna-2026-10"
        assert out["terminal_reason"] == "ok"
        # Nothing that was there before moved.
        assert out["resolved_model"] == "gpt-6-luna" and out["review_outcome"] == "LGTM"

    def test_pre_007_row_serializes_none(self):
        out = web._serialize(_job(resolved_provider=None, model_served=None,
                                  terminal_reason=None)).model_dump()
        assert out["resolved_provider"] is None
        assert out["model_served"] is None
        assert out["terminal_reason"] is None

    def test_list_jobs_returns_provider(self, client, monkeypatch):
        rows = [_job(), _job(resolved_provider="anthropic", resolved_model="claude-opus-4-7",
                             model_served=None)]

        class _DB:
            def __call__(self):
                return self

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def execute(self, stmt):
                return SimpleNamespace(scalars=lambda: iter(rows))

        monkeypatch.setattr(web, "async_session", _DB())
        body = client.get("/api/jobs").json()
        assert [r["resolved_provider"] for r in body] == ["codex", "anthropic"]
        assert body[1]["model_served"] is None


class TestJobsTableColumn:
    def test_table_has_a_provider_column_rendered_from_the_row(self):
        html = web._INDEX_HTML
        assert "<th>Provider</th>" in html
        assert "r.resolved_provider" in html

    def test_esc_helper_escapes_quotes_for_attribute_contexts(self):
        # model_served (vendor-stream data) is rendered inside title="...";
        # esc() must neutralise both quote kinds, not just <, > and &.
        html = web._INDEX_HTML
        m = re.search(r"function esc\(s\) \{ return \(s \|\| \"\"\)\.replace\((/\[[^\]]+\]/g), c => \(\{(.*?)\}\[c\]\)\); \}", html)
        assert m, "esc() helper not found"
        char_class, mapping = m.group(1), m.group(2)
        for ch in "<>&\"'":
            assert ch in char_class
        assert "&quot;" in mapping and "&#39;" in mapping


class TestModelSelectGroupedByProvider:
    def test_default_first_then_one_optgroup_per_enabled_provider(self):
        html = web._model_options_html(enabled=frozenset({"anthropic", "codex"}))
        assert html.startswith('<option value="">default</option>')
        groups = re.findall(r'<optgroup label="([^"]+)">', html)
        assert groups == ["anthropic", "codex"]          # models.yml order
        assert html.count("</optgroup>") == 2

    def test_options_sit_inside_their_provider_group(self):
        html = web._model_options_html(enabled=frozenset({"anthropic", "codex"}))
        a = html.index('<optgroup label="anthropic">')
        c = html.index('<optgroup label="codex">')
        assert a < html.index('value="claude-sonnet-4-6"') < c
        assert c < html.index('value="codex/gpt-6-luna"')
        # Every codex model, labelled from the registry, in yml order.
        codex_ids = [m.ref.canonical for m in reg.list_models("codex")]
        positions = [html.index(f'value="{cid}"') for cid in codex_ids]
        assert positions == sorted(positions)
        assert "gpt-6 luna (budget)" in html

    def test_disabled_provider_has_no_group(self):
        html = web._model_options_html(enabled=frozenset({"anthropic"}))
        assert re.findall(r'<optgroup label="([^"]+)">', html) == ["anthropic"]
        assert "codex" not in html

    def test_served_page_is_grouped(self):
        assert '<optgroup label="anthropic">' in web._INDEX_HTML
