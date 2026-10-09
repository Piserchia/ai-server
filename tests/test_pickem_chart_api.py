"""The pickem-chart skill's helper script: the description parser, the token
read (never echoed), and the exact requests it builds."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "pickem-chart" / "chart_api.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("chart_api", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("text, expected", [
    ("pickem-chart request=17", 17),
    ("pickem-chart request=0017", 17),
    ("  pickem-chart request=3  ", 3),
    ("pickem-chart request=", None),
    ("pickem-analysis player=1 through_week=2", None),
    ("pickem-chart request=abc", None),
    ("", None),
])
def test_parse_description(mod, text, expected):
    assert mod.parse_description(text) == expected


def test_read_admin_token_handles_quotes_and_equals(mod, tmp_path):
    env = tmp_path / ".env"
    env.write_text('PICKEM_GATEWAY_TOKEN=should-not-matter\nPICKEM_ADMIN_TOKEN="ab=cd"\n')
    assert mod.read_admin_token(str(env)) == "ab=cd"
    env.write_text("PICKEM_ADMIN_TOKEN='x'\n")
    assert mod.read_admin_token(str(env)) == "x"


def test_read_admin_token_missing_is_fatal(mod, tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\n")
    with pytest.raises(SystemExit):
        mod.read_admin_token(str(env))


def test_build_requests(mod):
    assert mod.build("get", 5) == ("GET", "/api/internal/chart-requests/5", None)
    assert mod.build("stats", 5, player_id=9) == ("GET", "/api/players/9", None)
    m, p, body = mod.build("preview", 5, sql="SELECT 1")
    assert (m, p, json.loads(body)) == ("POST", "/api/internal/chart-requests/5/preview", {"sql": "SELECT 1"})
    m, p, body = mod.build("complete", 5, spec={"version": 1}, model="claude-opus-5")
    assert (m, p, json.loads(body)) == ("POST", "/api/internal/chart-requests/5/complete", {"spec": {"version": 1}, "model": "claude-opus-5"})
    m, p, body = mod.build("fail", 5, message="no")
    assert (m, p, json.loads(body)) == ("POST", "/api/internal/chart-requests/5/fail", {"message": "no"})


def test_main_never_prints_the_token(mod, tmp_path, monkeypatch, capsys):
    env_dir = tmp_path / "projects" / "pickem"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("PICKEM_ADMIN_TOKEN=supersecret\n")
    monkeypatch.setenv("SERVER_ROOT", str(tmp_path))
    seen = {}

    class Resp:
        status = 200
        def read(self): return b'{"ok": true}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout):
        seen["headers"] = dict(req.header_items())
        seen["url"] = req.full_url
        return Resp()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    rc = mod.main(["get", "5"])
    out = capsys.readouterr().out
    assert rc == 0 and "supersecret" not in out and '"ok": true' in out
    assert seen["headers"]["X-admin-token"] == "supersecret"
    assert seen["url"] == "http://localhost:8793/api/internal/chart-requests/5"


def test_main_preview_missing_sql_file_prints_clean_detail(mod, tmp_path, monkeypatch, capsys):
    env_dir = tmp_path / "projects" / "pickem"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("PICKEM_ADMIN_TOKEN=supersecret\n")
    monkeypatch.setenv("SERVER_ROOT", str(tmp_path))
    missing = tmp_path / "does-not-exist.sql"

    with pytest.raises(SystemExit) as exc_info:
        mod.main(["preview", "5", "--sql-file", str(missing)])
    out = capsys.readouterr().out
    assert exc_info.value.code == 2
    assert json.loads(out) == {"detail": f"sql-file not found: {missing}"}


def test_main_stats_missing_player_id_key_prints_clean_detail(mod, tmp_path, monkeypatch, capsys):
    env_dir = tmp_path / "projects" / "pickem"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("PICKEM_ADMIN_TOKEN=supersecret\n")
    monkeypatch.setenv("SERVER_ROOT", str(tmp_path))

    class Resp:
        status = 200
        def read(self): return b'{"id": 5}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda req, timeout: Resp())
    rc = mod.main(["stats", "5"])
    out = capsys.readouterr().out
    assert rc == 1
    assert json.loads(out)["detail"].startswith("get response missing player_id")


def test_main_stats_with_two_sequential_responses(mod, tmp_path, monkeypatch, capsys):
    """Test the stats command with two sequential fake responses."""
    env_dir = tmp_path / "projects" / "pickem"
    env_dir.mkdir(parents=True)
    (env_dir / ".env").write_text("PICKEM_ADMIN_TOKEN=supersecret\n")
    monkeypatch.setenv("SERVER_ROOT", str(tmp_path))
    call_count = {"count": 0}

    class Resp:
        def __init__(self, status, body):
            self.status = status
            self.body = body

        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout):
        call_count["count"] += 1
        if call_count["count"] == 1:
            # First call: get request to retrieve player_id
            return Resp(200, b'{"player_id": 42}')
        else:
            # Second call: get stats for the player
            return Resp(200, b'{"player_name": "Alice", "stats": []}')

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    rc = mod.main(["stats", "5"])
    out = capsys.readouterr().out
    assert rc == 0 and "supersecret" not in out
    assert call_count["count"] == 2
