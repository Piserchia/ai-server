"""Tests for scripts/lib.py — the design-document library.

Fixture corpus: tests/fixtures/library/ (two specs forming a superseded pair,
one plan, one charter). The last test runs `check` against the REAL repo root
so the deploy gate fails when a front-matter block or docs/LIBRARY.md goes
stale.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import scripts.lib as lib  # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "library"
LIB_PY = REPO_ROOT / "scripts" / "lib.py"


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A writable copy of the fixture corpus."""
    dst = tmp_path / "root"
    shutil.copytree(FIXTURES, dst)
    return dst


def _run(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(LIB_PY), "--root", str(root), *args],
        capture_output=True, text=True,
    )


# ── front-matter parse ───────────────────────────────────────────────────────

def test_front_matter_parses_every_fixture(corpus: Path):
    docs = lib.load_docs(corpus)
    ids = sorted(d.id for d in docs)
    assert ids == [
        "charter-widgets", "plan-2026-01-05-gamma",
        "spec-2026-01-01-alpha", "spec-2026-02-02-beta",
    ]
    assert all(d.errors == [] for d in docs)
    alpha = lib.by_id(docs)["spec-2026-01-01-alpha"]
    assert alpha.fm["date"] == "2026-01-01"  # yaml date normalised to str
    assert alpha.body.lstrip().startswith("# Alpha design")


def test_missing_front_matter_is_a_finding(corpus: Path):
    (corpus / "docs" / "naked.md").write_text("# No block here\n")
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("docs/naked.md" in f and "no front-matter" in f for f in findings)


# ── id rules ─────────────────────────────────────────────────────────────────

def test_duplicate_id_is_a_finding(corpus: Path):
    src = corpus / "docs" / "superpowers" / "plans" / "2026-01-05-gamma.md"
    text = src.read_text()
    (corpus / "docs" / "superpowers" / "plans" / "2026-01-06-gamma.md").write_text(text)
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("duplicate id `plan-2026-01-05-gamma`" in f for f in findings)
    # the copy also violates the filename-stem rule
    assert any("must be `plan-2026-01-06-gamma`" in f for f in findings)


def test_id_regex_per_type(corpus: Path):
    plan = corpus / "docs" / "superpowers" / "plans" / "2026-01-05-gamma.md"
    plan.write_text(plan.read_text().replace("id: plan-2026-01-05-gamma", "id: plan-gamma"))
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("`plan-gamma` must match `plan-<YYYY-MM-DD>-<slug>`" in f for f in findings)
    charter = corpus / ".context" / "org" / "divisions" / "widgets" / "CHARTER.md"
    charter.write_text(charter.read_text().replace("id: charter-widgets", "id: guide-widgets"))
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("`guide-widgets` must match `charter-<slug>`" in f for f in findings)


# ── vocabulary ───────────────────────────────────────────────────────────────

def test_status_and_type_vocabulary(corpus: Path):
    plan = corpus / "docs" / "superpowers" / "plans" / "2026-01-05-gamma.md"
    plan.write_text(plan.read_text().replace("status: shipped", "status: done"))
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("status `done` not in" in f for f in findings)
    plan.write_text(plan.read_text().replace("type: plan", "type: memo"))
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("type `memo` not in" in f for f in findings)


# ── supersession symmetry ────────────────────────────────────────────────────

def test_supersession_symmetric_corpus_is_clean(corpus: Path):
    assert lib.validate_docs(lib.load_docs(corpus)) == []


def test_supersession_must_agree_both_ways(corpus: Path):
    beta = corpus / "docs" / "superpowers" / "specs" / "2026-02-02-beta-design.md"
    beta.write_text(beta.read_text().replace("supersedes: [spec-2026-01-01-alpha]", "supersedes: []"))
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("superseded_by `spec-2026-02-02-beta` but that doc's supersedes list" in f
               for f in findings)


def test_superseded_by_requires_superseded_status(corpus: Path):
    alpha = corpus / "docs" / "superpowers" / "specs" / "2026-01-01-alpha-design.md"
    alpha.write_text(alpha.read_text().replace("status: superseded", "status: accepted"))
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("has superseded_by but status is `accepted`" in f for f in findings)


def test_unknown_superseded_by_is_a_finding(corpus: Path):
    alpha = corpus / "docs" / "superpowers" / "specs" / "2026-01-01-alpha-design.md"
    alpha.write_text(alpha.read_text().replace(
        "superseded_by: spec-2026-02-02-beta", "superseded_by: spec-2026-03-03-ghost"))
    findings = lib.validate_docs(lib.load_docs(corpus))
    assert any("superseded_by unknown id `spec-2026-03-03-ghost`" in f for f in findings)


# ── index regeneration ───────────────────────────────────────────────────────

def test_index_then_check_round_trip(corpus: Path):
    missing = _run(corpus, "check")
    assert missing.returncode == 2
    assert missing.stdout.strip().splitlines()[-1].startswith("LIB CHECK FAIL")
    assert "docs/LIBRARY.md missing" in missing.stdout

    idx = _run(corpus, "index")
    assert idx.returncode == 0, idx.stdout + idx.stderr
    assert idx.stdout.strip().splitlines()[-1].startswith("LIB INDEX OK")
    lib_md = (corpus / "docs" / "LIBRARY.md").read_text()
    assert lib_md == lib.render_library(lib.load_docs(corpus))
    assert lib_md.rstrip().endswith(lib.FOOTER)
    assert "| id | status | date | summary | path |" in lib_md
    assert "~~`spec-2026-01-01-alpha`~~ → `spec-2026-02-02-beta`" in lib_md
    # newest first within a type
    assert lib_md.index("spec-2026-02-02-beta") < lib_md.index("~~`spec-2026-01-01-alpha`")
    # LIBRARY.md itself is never scanned
    assert not any(d.rel == "docs/LIBRARY.md" for d in lib.load_docs(corpus))

    ok = _run(corpus, "check")
    assert ok.returncode == 0, ok.stdout
    assert ok.stdout.strip().splitlines()[-1] == "LIB CHECK OK"

    # a status edit without re-indexing makes the committed index stale
    plan = corpus / "docs" / "superpowers" / "plans" / "2026-01-05-gamma.md"
    plan.write_text(plan.read_text().replace("status: shipped", "status: built"))
    stale = _run(corpus, "check")
    assert stale.returncode == 2
    assert "docs/LIBRARY.md is stale" in stale.stdout
    assert stale.stdout.strip().splitlines()[-1] == "LIB CHECK FAIL (1 findings)"


# ── show / status / grep ─────────────────────────────────────────────────────

def test_show_section_by_number_returns_exactly_one_section(corpus: Path):
    out = _run(corpus, "show", "spec-2026-01-01-alpha", "--section", "2")
    assert out.returncode == 0, out.stdout
    assert out.stdout == (
        "## 2) Decisions\n\n| D | Decision |\n|---|---|\n| D1 | widgets are blue |\n\n"
        "### 2a) Sub-decision\n\nNested detail about widgets.\n"
    )
    # `2` does not match `2a` (number must not be followed by a digit/letter)
    assert "## 3)" not in out.stdout
    sub = _run(corpus, "show", "spec-2026-01-01-alpha", "--section", "2a")
    assert sub.stdout == "### 2a) Sub-decision\n\nNested detail about widgets.\n"


def test_show_section_by_heading_substring_ignores_fences(corpus: Path):
    out = _run(corpus, "show", "spec-2026-02-02-beta", "--section", "purpose")
    assert out.returncode == 0
    assert out.stdout.startswith("## 1) Purpose\n")
    assert "## not a heading" in out.stdout  # fenced text is body, not a boundary
    assert "## 2) Decisions" not in out.stdout
    nope = _run(corpus, "show", "spec-2026-02-02-beta", "--section", "nonexistent")
    assert nope.returncode == 1
    assert nope.stdout.startswith("LIB SHOW FAIL")


def test_show_whole_doc_and_unknown_id(corpus: Path):
    out = _run(corpus, "show", "plan-2026-01-05-gamma")
    assert out.returncode == 0
    assert out.stdout.lstrip().startswith("# Gamma plan")
    assert "---\nid:" not in out.stdout
    bad = _run(corpus, "show", "plan-does-not-exist")
    assert bad.returncode == 1
    assert bad.stdout.startswith("LIB SHOW FAIL: unknown id")


def test_status_one_line(corpus: Path):
    out = _run(corpus, "status", "spec-2026-01-01-alpha")
    assert out.returncode == 0
    lines = out.stdout.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("spec-2026-01-01-alpha: superseded — superseded by spec-2026-02-02-beta")
    beta = _run(corpus, "status", "spec-2026-02-02-beta").stdout
    assert "supersedes spec-2026-01-01-alpha" in beta


def test_grep_returns_id_tagged_paragraphs(corpus: Path):
    out = _run(corpus, "grep", "WIDGETS")
    assert out.returncode == 0
    blocks = [b for b in out.stdout.strip().split("\n\n") if b]
    assert blocks, out.stdout
    for b in blocks:
        first = b.splitlines()[0]
        assert " §" in first, first
        assert first.split(" §")[0] in {
            "spec-2026-01-01-alpha", "spec-2026-02-02-beta",
            "plan-2026-01-05-gamma", "charter-widgets",
        }
        assert "widget" in b.lower()
    assert any(b.startswith("spec-2026-01-01-alpha §1) Purpose") for b in blocks)
    capped = _run(corpus, "grep", "widgets", "--max", "1")
    assert len([b for b in capped.stdout.strip().split("\n\n") if b]) == 1
    none = _run(corpus, "grep", "zzz-no-such-term")
    assert none.returncode == 1


# ── the real repo ────────────────────────────────────────────────────────────

def test_real_repo_check_is_clean():
    out = _run(REPO_ROOT, "check")
    assert out.returncode == 0, out.stdout
    assert out.stdout.strip().splitlines()[-1] == "LIB CHECK OK"
