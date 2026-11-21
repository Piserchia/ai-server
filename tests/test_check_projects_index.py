"""Tests for scripts/check_projects_index.py — the combined project index check."""

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.check_projects_index as cpi  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


# ── the committed index ─────────────────────────────────────────────────────

def test_committed_index_has_no_errors():
    """The committed index agrees with the committed _ports.yml, registry and
    Caddy snippets. Missing manifests are warnings off the Mini."""
    rep = cpi.run(REPO_ROOT)
    assert rep.errors == []


def test_committed_index_covers_every_registry_slug():
    index = cpi.load_index(REPO_ROOT / cpi.INDEX_REL)
    slugs = {p["slug"] for p in index["projects"]}
    registry = set(cpi.load_registry_slugs(REPO_ROOT / ".context" / "PROJECTS_REGISTRY.md"))
    assert registry and registry == slugs


# ── a small synthetic tree ──────────────────────────────────────────────────

def _project(slug, port, **extra):
    p = {
        "slug": slug, "name": slug.title(), "status": "live", "type": "service",
        "topology": "dev-repo", "dev_clone": f"~/Documents/repos/{slug}",
        "hostname": f"{slug}.example.com", "port": port, "healthcheck": "/healthz",
        "services": [{"name": slug, "port": port}],
        "deploy": {"skill": "project-redeploy", "autonomy": "gated-auto",
                   "command": f"/task deploy-director: {slug}"},
        "health": {"command": f"curl -fsS http://127.0.0.1:{port}/healthz"},
        "manifest": {"location": "mini"}, "verified": "test",
    }
    p.update(extra)
    return p


def _tree(tmp_path, projects, ports=None, registry=None, caddy=None):
    (tmp_path / ".context").mkdir()
    (tmp_path / "projects").mkdir()
    (tmp_path / "Caddyfile.d").mkdir()
    index = {"version": 1, "domain": "example.com",
             "core": {"ports": [{"port": 8080, "service": "web-gateway"}], "hostnames": []},
             "projects": projects}
    (tmp_path / cpi.INDEX_REL).write_text(yaml.safe_dump(index))
    if ports is None:
        ports = {8080: "web-gateway", **{p["port"]: p["slug"] for p in projects if p.get("port")}}
    (tmp_path / "projects" / "_ports.yml").write_text(
        "# header\n" + "".join(f"{k}: {v}   # note\n" for k, v in ports.items()))
    slugs = registry if registry is not None else [p["slug"] for p in projects]
    rows = "".join(f"| `{s}` | service | x |\n" for s in slugs)
    (tmp_path / ".context" / "PROJECTS_REGISTRY.md").write_text(
        "# Projects Registry\n\n## Currently hosted\n\n| Slug | Type | X |\n|---|---|---|\n"
        + rows + "\n## Other\n\n| `not-a-project` | x |\n")
    for name, body in (caddy or {}).items():
        (tmp_path / "Caddyfile.d" / name).write_text(body)
    return tmp_path


def _manifest(tmp_path, dirname, data):
    d = tmp_path / "projects" / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.yml").write_text(yaml.safe_dump(data))


def _good_manifest(slug, port):
    return {
        "slug": slug, "type": "service", "subdomain": slug, "port": port,
        "healthcheck": "/healthz",
        "delivery": {"topology": "dev-repo", "dev_repo": f"~/Documents/repos/{slug}",
                     "runtime_clone": "pull-only",
                     "deploy": {"skill": "project-redeploy", "autonomy": "gated-auto",
                                "services": [slug]}},
    }


def test_clean_tree_passes(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001), _project("beta", 9002)])
    rep = cpi.run(root)
    assert rep.errors == []
    assert any("manifest not readable" in w for w in rep.warnings)


def test_duplicate_port_is_an_error(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001), _project("beta", 9001)],
                 ports={8080: "web-gateway", 9001: "alpha"})
    rep = cpi.run(root)
    assert any("port 9001 claimed by both" in e for e in rep.errors)


def test_port_missing_from_ports_file_is_an_error(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)], ports={8080: "web-gateway"})
    rep = cpi.run(root)
    assert any("does not allocate it" in e for e in rep.errors)


def test_ports_file_entry_missing_from_index_is_an_error(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)],
                 ports={8080: "web-gateway", 9001: "alpha", 9002: "ghost"})
    rep = cpi.run(root)
    assert any("9002" in e and "ghost" in e for e in rep.errors)


def test_retired_port_reuse_is_an_error(tmp_path):
    old = _project("old", None, status="retired", hostname=None, services=[],
                   retired_ports=[9001], manifest={"location": "github"})
    root = _tree(tmp_path, [old, _project("alpha", 9001)])
    rep = cpi.run(root)
    assert any("retired by `old`" in e for e in rep.errors)


def test_registry_drift_is_an_error(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)], registry=["alpha", "beta"])
    rep = cpi.run(root)
    assert any("`beta` is in PROJECTS_REGISTRY.md" in e for e in rep.errors)


def test_duplicate_hostname_is_an_error(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001),
                            _project("beta", 9002, hostname="alpha.example.com")])
    rep = cpi.run(root)
    assert any("hostname alpha.example.com claimed by both" in e for e in rep.errors)


def test_caddy_snippet_on_wrong_port_is_an_error(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)], caddy={
        "alpha.conf": "http://alpha.example.com {\n    handle {\n        reverse_proxy localhost:9999\n    }\n}\n"})
    rep = cpi.run(root)
    assert any("sends alpha.example.com to :9999" in e for e in rep.errors)


def test_caddy_snippet_for_unknown_host_is_an_error(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)], caddy={
        "zed.conf": "http://zed.example.com {\n    reverse_proxy localhost:9001\n}\n"})
    rep = cpi.run(root)
    assert any("zed.example.com" in e for e in rep.errors)


def test_matching_manifest_passes(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)])
    _manifest(root, "alpha", _good_manifest("alpha", 9001))
    rep = cpi.run(root, strict=True)
    assert rep.errors == []


def test_manifest_drift_is_reported(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)])
    m = _good_manifest("alpha", 9002)
    m["delivery"]["deploy"]["services"] = ["alpha", "alpha-worker"]
    _manifest(root, "alpha", m)
    rep = cpi.run(root)
    assert any("index port is 9001" in e for e in rep.errors)
    assert any("index services" in e for e in rep.errors)


def test_manifest_override_path_is_used(tmp_path):
    root = _tree(tmp_path, [_project("alpha", 9001)])
    elsewhere = tmp_path / "elsewhere.yml"
    elsewhere.write_text(yaml.safe_dump(_good_manifest("alpha", 9001)))
    rep = cpi.run(root, overrides={"alpha": elsewhere}, strict=True)
    assert rep.errors == []


def test_strict_makes_missing_manifest_an_error_except_retired(tmp_path):
    old = _project("old", None, status="retired", hostname=None, services=[],
                   manifest={"location": "github"})
    root = _tree(tmp_path, [old, _project("alpha", 9001)])
    rep = cpi.run(root, strict=True)
    assert any(e.startswith("alpha: manifest not readable") for e in rep.errors)
    assert not any(e.startswith("old:") for e in rep.errors)


def test_content_project_with_a_manifest_is_an_error(tmp_path):
    notes = _project("notes", None, status="content", type="content", topology="content",
                     hostname=None, services=[], manifest={"location": "none"})
    root = _tree(tmp_path, [notes])
    _manifest(root, "notes", {"slug": "notes", "type": "static", "subdomain": "notes"})
    rep = cpi.run(root)
    assert any("index says it has no manifest" in e for e in rep.errors)


def test_live_project_missing_deploy_command_is_an_error(tmp_path):
    p = _project("alpha", 9001)
    p["deploy"] = {"skill": "project-redeploy", "autonomy": "gated-auto"}
    root = _tree(tmp_path, [p])
    rep = cpi.run(root)
    assert any("deploy.command" in e for e in rep.errors)


def test_cli_exit_code(tmp_path, capsys):
    root = _tree(tmp_path, [_project("alpha", 9001), _project("beta", 9001)],
                 ports={8080: "web-gateway", 9001: "alpha"})
    assert cpi.main(["--root", str(root)]) == 1
    assert "ERROR" in capsys.readouterr().out
