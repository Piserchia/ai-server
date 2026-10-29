"""
E2 — AskUserQuestion is off the DEFAULT tool list (spec §3/§9; TROUBLESHOOTING
"Root cause #5": nothing consumes the question headless, so the job hangs in
`running`). One definition — `registry.skills.DEFAULT_REQUIRED_TOOLS` — feeds the
dataclass default, the loader fallback and the generic (no-skill) session.
Skills that declare `required_tools` explicitly are untouched (7 name
AskUserQuestion today, incl. the protected `skills/new-skill/SKILL.md`), and so
are the subagents of such skills (`agents.py` reads `cfg.required_tools`).

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_default_tools.py -q
"""

from __future__ import annotations

import inspect

from src.registry.skills import DEFAULT_REQUIRED_TOOLS, SkillConfig, load


def test_default_list_has_no_ask_user_question():
    assert "AskUserQuestion" not in DEFAULT_REQUIRED_TOOLS
    assert DEFAULT_REQUIRED_TOOLS == ("Read", "Write", "Edit", "Bash", "Glob", "Grep",
                                      "WebSearch", "WebFetch")
    assert isinstance(DEFAULT_REQUIRED_TOOLS, tuple)       # one immutable definition


def test_dataclass_default_uses_the_constant():
    cfg = SkillConfig(name="x", body="")
    assert cfg.required_tools == list(DEFAULT_REQUIRED_TOOLS)
    # A fresh list per instance, never the shared tuple or a shared list.
    cfg.required_tools.append("Extra")
    assert SkillConfig(name="y", body="").required_tools == list(DEFAULT_REQUIRED_TOOLS)


def _skill(tmp_path, frontmatter: str):
    (tmp_path / "t").mkdir()
    (tmp_path / "t" / "SKILL.md").write_text(f"---\n{frontmatter}\n---\nbody\n")
    return load("t", skills_dir=tmp_path)


def test_loader_fallback_uses_the_constant(tmp_path):
    cfg = _skill(tmp_path, "name: t\ndescription: d")
    assert cfg.required_tools == list(DEFAULT_REQUIRED_TOOLS)


def test_explicit_declaration_still_honoured(tmp_path):
    cfg = _skill(tmp_path, "name: t\ndescription: d\nrequired_tools: [Read, AskUserQuestion]")
    assert cfg.required_tools == ["Read", "AskUserQuestion"]


def test_session_generic_default_uses_the_constant():
    # The generic (no-skill) task built its own literal list in _build_options;
    # the literal is gone and the constant is what it reads.
    from src.runner import session
    src = inspect.getsource(session._build_options)
    assert "AskUserQuestion" not in src
    assert "DEFAULT_REQUIRED_TOOLS" in src


def test_no_other_default_literal_survives():
    # The three sites were three copies of one list; after E2 the only place
    # the eight-name default is spelled out is the constant itself.
    import pathlib
    from src.registry import skills as skills_mod
    from src.runner import session as session_mod
    for mod in (skills_mod, session_mod):
        src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        occurrences = src.count('"WebSearch", "WebFetch"')
        assert occurrences == (1 if mod is skills_mod else 0), mod.__name__
