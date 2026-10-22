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


class TestJobOutOriginFields:
    """A2: `JobOut`/`_serialize` expose the 008 origin + queue-wait columns
    (additive, `getattr(..., None)` like the 007 trio)."""

    def test_jobout_carries_origin_and_queue_wait(self):
        assert {"origin_channel", "origin_ref", "queue_wait_ms"} <= set(web.JobOut.model_fields)
        out = web._serialize(_job(origin_channel="telegram", origin_ref="123456789",
                                  queue_wait_ms=2500)).model_dump()
        assert out["origin_channel"] == "telegram"
        assert out["origin_ref"] == "123456789"
        assert out["queue_wait_ms"] == 2500
        # Nothing that was there before moved.
        assert out["resolved_provider"] == "codex" and out["terminal_reason"] == "ok"

    def test_pre_008_row_serializes_none(self):
        # The `_job()` stand-in carries none of the three attributes.
        out = web._serialize(_job()).model_dump()
        assert out["origin_channel"] is None
        assert out["origin_ref"] is None
        assert out["queue_wait_ms"] is None


def test_jobout_carries_token_and_cost_columns():
    """B3: the 008 result-capture columns are on `JobOut`/`_serialize`
    (getattr idiom; the two cost columns serialise as floats)."""
    from decimal import Decimal
    cols = {"input_tokens", "output_tokens", "cache_read_tokens", "cache_write_1h_tokens",
            "cache_write_5m_tokens", "num_turns", "duration_api_ms", "cost_usd_list",
            "sdk_cost_usd", "cli_version"}
    assert cols <= set(web.JobOut.model_fields)
    out = web._serialize(_job(
        input_tokens=1200, output_tokens=300, cache_read_tokens=5000,
        cache_write_1h_tokens=800, cache_write_5m_tokens=0, num_turns=4,
        duration_api_ms=15000, cost_usd_list=Decimal("3.4850"), sdk_cost_usd=3.49,
        cli_version="2.1.139")).model_dump()
    assert (out["input_tokens"], out["output_tokens"], out["cache_read_tokens"],
            out["cache_write_1h_tokens"], out["cache_write_5m_tokens"]) == (1200, 300, 5000, 800, 0)
    assert out["num_turns"] == 4 and out["duration_api_ms"] == 15000
    assert out["cost_usd_list"] == 3.485 and isinstance(out["cost_usd_list"], float)
    assert out["sdk_cost_usd"] == 3.49
    assert out["cli_version"] == "2.1.139"
    # A pre-008 row (the stand-in carries none of them) serialises None.
    out = web._serialize(_job()).model_dump()
    assert all(out[c] is None for c in cols)
    # The jobs table shows cost + turns from the row.
    assert "r.cost_usd_list" in web._INDEX_HTML and "r.num_turns" in web._INDEX_HTML
