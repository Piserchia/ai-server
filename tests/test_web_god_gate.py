"""POST /api/jobs must reject kind='god' (2026-08-31 review catch).

Telegram /god is the single break-glass door (INV-18): the dispatch MCP and
/task --kind=god were closed in the F1 hardening; the web API was the third
door — any unisolated skill able to read WEB_AUTH_TOKEN could have posted a
kind=god job. The rejection fires before auth-independent side effects
(no DB row, no Redis push).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.gateway import web


@pytest.fixture()
def client():
    web.app.dependency_overrides[web._check_auth] = lambda: None
    try:
        yield TestClient(web.app)
    finally:
        web.app.dependency_overrides.pop(web._check_auth, None)


def test_kind_god_rejected_403(client):
    r = client.post("/api/jobs", json={"kind": "god", "description": "own the box"})
    assert r.status_code == 403
    assert "/god" in r.json()["detail"]


def test_kind_god_rejected_case_and_whitespace(client):
    r = client.post("/api/jobs", json={"kind": " God ", "description": "x"})
    assert r.status_code == 403
