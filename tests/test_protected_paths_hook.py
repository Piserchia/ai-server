"""
E9 — the dev protected-path commit-msg guard (spec §6, §9 Phase-1 row
"`install-dev-hooks.sh` + `test_protected_paths_hook`"; design of record P0
plan Task 13 Step 6c + the re-cut E9 Deltas).

"Protected path" was prose: MISSION §M lists them and the dev repo's only hook
enforced a CHANGELOG on `src/`. `scripts/install-dev-hooks.sh install` arms a
`commit-msg` hook (the ONE hook git hands the message file to as `$1`) that
refuses a staged diff touching a §M path unless the message carries
`Approved-Protected-Path: ap-<id>`. `check <paths-file> <message-file>` is the
pure decision, driven here with fixtures — no git, no DB, no network (the
install test uses a throwaway `git init`).

Phase-1 limit, stated by the script itself: the id's SHAPE is checked; resolving
it against `approvals(kind=protected_path)` begins with the Phase-2 approvals
migration (009). The guard notices a missing approval; it is not the approval.

Run: PIPENV_DONT_LOAD_ENV=1 SERVER_ROOT="$PWD" pipenv run pytest tests/test_protected_paths_hook.py -q
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "install-dev-hooks.sh"


def _check(tmp_path, paths: list[str], message: str):
    p = tmp_path / "paths"
    p.write_text("\n".join(paths) + "\n")
    m = tmp_path / "msg"
    m.write_text(message)
    return subprocess.run(["bash", str(SCRIPT), "check", str(p), str(m)],
                          capture_output=True, text=True)


def _patterns() -> list[str]:
    block = SCRIPT.read_text(encoding="utf-8").split("PROTECTED_PATTERNS=(")[1].split(")")[0]
    return [ln.strip().strip("'") for ln in block.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def _mission_section_m() -> str:
    text = (REPO / "MISSION.md").read_text(encoding="utf-8")
    start = text.index("### M. Safety ceilings")
    end = text.find("\n### ", start + 1)
    return text[start:end if end != -1 else None]


def test_ordinary_commit_passes(tmp_path):
    r = _check(tmp_path, ["src/runner/session.py", "tests/test_x.py", "docs/x.md"], "feat: x\n")
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""


@pytest.mark.parametrize("path", sorted(set(_patterns())))
def test_every_protected_path_is_refused_without_a_trailer(tmp_path, path):
    # Parametrized over the list the script reads — which the two-way test
    # below pins to MISSION §M.
    r = _check(tmp_path, [path], "fix: sneak it in\n")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "REFUSED" in r.stderr and path in r.stderr


def test_a_nested_copy_of_a_protected_path_is_refused_too(tmp_path):
    # `*/MISSION.md` — a protected file inside a project clone or a vendored copy.
    r = _check(tmp_path, ["projects/x/MISSION.md"], "chore: x\n")
    assert r.returncode == 1


def test_a_valid_trailer_allows_it(tmp_path):
    r = _check(tmp_path, ["MISSION.md"],
               "docs: MISSION §M update\n\nApproved-Protected-Path: ap-7f3a91\n")
    assert r.returncode == 0, r.stderr
    assert "ap-7f3a91" in r.stderr


@pytest.mark.parametrize("bad", [
    "Approved-Protected-Path:\n",                    # no id
    "Approved-Protected-Path: ap-\n",                # empty id
    "Approved-Protected-Path: 7f3a91\n",             # missing ap- prefix
    "approved-protected-path: ap-7f3a91\n",          # wrong case
    "Approved-Protected-Path: ap-7f3a91 extra\n",    # not a trailer
    "Approved-Protected-Path: ap-7f\n",              # too short to be an id
])
def test_a_malformed_trailer_does_not_count(tmp_path, bad):
    assert _check(tmp_path, [".env"], f"fix: x\n\n{bad}").returncode == 1


def test_the_list_is_missions_list():
    """TWO-WAY against MISSION §M as it reads today. Direction 1: nothing is
    guarded that §M does not name (one item is named by description — "the
    chat-ID/web-auth checks" is `_check_auth` in src/gateway/web.py).
    Direction 2: every PATH §M names is guarded; the §M items that are not
    paths (deleting a project/skill directory; the TELEGRAM_ALLOWED_CHAT_IDS
    env NAME, which lives in `.env`) are listed as explicit exceptions.
    D6's first half (an owner PR) adds `.claude/settings.json`,
    `.claude/settings.local.json` and this script's own path list to §M —
    when it lands, this test fails in direction 2 and the list grows
    deliberately."""
    section = _mission_section_m()
    patterns = _patterns()
    by_description = {"src/gateway/web.py": "chat-ID/web-auth checks",
                      "src/gateway/telegram_bot.py": "chat-ID/web-auth checks"}
    for pat in patterns:
        if pat in by_description:
            assert by_description[pat] in section, pat
            continue
        assert pat in section, f"{pat} is guarded here but not named in MISSION §M"
    # Every backticked path-shaped token in §M's numbered list must be guarded.
    numbered = section.split("Rationale:")[0]
    named_paths = {m for m in re.findall(r"`([^`\s]+)`", numbered)
                   if "/" in m or m.endswith(".md") or m == ".env"}
    named_paths.discard("TELEGRAM_ALLOWED_CHAT_IDS")
    named_paths = {p.split("/", 1)[1] if p.startswith(".env/") else p for p in named_paths}
    missing = sorted(named_paths - set(patterns))
    assert not missing, f"MISSION §M names these and the guard does not cover them: {missing}"
    assert "src/gateway/web.py" in patterns and ".context/org/ORG.md" in patterns
    assert "src/gateway/telegram_bot.py" in patterns          # the chat-ID half of §M item 2


def test_install_targets_commit_msg_and_reads_the_message_argument():
    """The mechanism, pinned: git passes a PRE-COMMIT hook no arguments and
    `.git/COMMIT_EDITMSG` there still holds the PREVIOUS commit's message, so a
    pre-commit trailer check refuses approved commits and allows unapproved
    ones whose predecessor carried the trailer. commit-msg is the hook git
    hands the message file as $1."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "/hooks/commit-msg" in src
    installer = src.split("cmd_install()")[1].split("\ncase ")[0]
    assert "pre-commit" not in installer, "cmd_install must not touch the CHANGELOG pre-commit hook"
    assert "COMMIT_EDITMSG" not in src, "never read the message from COMMIT_EDITMSG"
    assert '"$1"' in installer or "\\$1" in installer, "the generated hook must pass its own $1 as the message file"
    # --no-renames: `git mv MISSION.md docs/OLD.md` otherwise lists only the
    # destination; T: a file replaced by a symlink is a typechange, which the
    # old filter excluded (whole-branch review 2026-10-29, reproduced).
    assert "git diff --cached --no-renames --name-only --diff-filter=ACMRDT" in src


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                          cwd=cwd, capture_output=True, text=True)


def test_install_is_idempotent_and_keeps_an_existing_hook(tmp_path):
    # Appending, never overwriting: a checkout may already have a commit-msg
    # hook; the CHANGELOG guard in .git/hooks/pre-commit is a different file
    # this installer must leave alone. GIT_DIR points the installer at a
    # throwaway repo so the test never touches this checkout's hooks.
    repo = tmp_path / "repo"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "commit-msg").write_text("#!/usr/bin/env bash\necho existing-hook-kept\n")
    (hooks / "pre-commit").write_text("#!/usr/bin/env bash\necho changelog-guard\n")
    env = {"GIT_DIR": str(repo / ".git"), "PATH": "/usr/bin:/bin"}
    for _ in range(2):
        r = subprocess.run(["bash", str(SCRIPT), "install"], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stderr
    hook = (hooks / "commit-msg").read_text()
    assert hook.count("ai-server protected-path guard >>>") == 1          # once, after two installs
    assert "echo existing-hook-kept" in hook                                # the prior hook survives
    assert (hooks / "pre-commit").read_text() == "#!/usr/bin/env bash\necho changelog-guard\n"
    assert (hooks / "commit-msg").stat().st_mode & 0o111                   # executable


def test_the_installed_hook_refuses_a_protected_commit_end_to_end(tmp_path):
    # The real thing: a throwaway repo with the hook installed, a staged
    # protected path, `git commit` → refused; with the trailer → allowed.
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "install-dev-hooks.sh").write_bytes(SCRIPT.read_bytes())
    (repo / "MISSION.md").write_text("# mission\n")
    (repo / "ok.txt").write_text("x\n")
    env = {"GIT_DIR": str(repo / ".git"), "PATH": "/usr/bin:/bin"}
    assert subprocess.run(["bash", "scripts/install-dev-hooks.sh", "install"], cwd=repo,
                          capture_output=True, text=True, env=env).returncode == 0
    _git(repo, "add", "ok.txt")
    assert _git(repo, "commit", "-q", "-m", "chore: ordinary").returncode == 0
    _git(repo, "add", "MISSION.md")
    refused = _git(repo, "commit", "-q", "-m", "docs: sneak")
    assert refused.returncode != 0 and "REFUSED" in refused.stderr
    allowed = _git(repo, "commit", "-q", "-m", "docs: approved\n\nApproved-Protected-Path: ap-7f3a91")
    assert allowed.returncode == 0, allowed.stderr
    # A rename of a protected file is refused (the SOURCE path is protected).
    _git(repo, "mv", "MISSION.md", "OLD.md")
    moved = _git(repo, "commit", "-q", "-m", "chore: move it")
    assert moved.returncode != 0 and "REFUSED" in moved.stderr, moved.stderr
    _git(repo, "reset", "-q", "--hard")
    # Replacing a protected file with a symlink (typechange) is refused.
    (repo / "MISSION.md").unlink()
    (repo / "MISSION.md").symlink_to("ok.txt")
    _git(repo, "add", "MISSION.md")
    typed = _git(repo, "commit", "-q", "-m", "chore: link it")
    assert typed.returncode != 0 and "REFUSED" in typed.stderr, typed.stderr


def test_the_auth_files_are_guarded_by_hunk_not_by_path(tmp_path):
    # Whole-branch review 2026-10-29: §M item 2 names "the chat-ID/web-auth
    # checks", not every line of web.py — plan §4 expects JobOut/route-body
    # edits without a trailer. The installed hook lists the two gateway files
    # only when their staged hunks touch an auth-check line.
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "src" / "gateway").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / "scripts" / "install-dev-hooks.sh").write_bytes(SCRIPT.read_bytes())
    web = repo / "src" / "gateway" / "web.py"
    web.write_text("def _check_auth(request):\n    return request.token == settings.web_auth_token\n\n"
                   "class JobOut:\n    id: str\n")
    env = {"GIT_DIR": str(repo / ".git"), "PATH": "/usr/bin:/bin"}
    assert subprocess.run(["bash", "scripts/install-dev-hooks.sh", "install"], cwd=repo,
                          capture_output=True, text=True, env=env).returncode == 0
    _git(repo, "add", "-A")
    assert _git(repo, "commit", "-q", "-m", "chore: initial — includes the auth check\n\nApproved-Protected-Path: ap-initial1").returncode == 0
    # A JobOut edit: no auth line in the hunk → allowed without a trailer.
    web.write_text(web.read_text() + "    model_served: str | None\n")
    _git(repo, "add", "src/gateway/web.py")
    r = _git(repo, "commit", "-q", "-m", "feat: JobOut.model_served")
    assert r.returncode == 0, r.stderr
    # Touching the auth check → refused.
    web.write_text(web.read_text().replace("return request.token == settings.web_auth_token",
                                           "return True  # _check_auth disabled"))
    _git(repo, "add", "src/gateway/web.py")
    r = _git(repo, "commit", "-q", "-m", "fix: loosen auth")
    assert r.returncode != 0 and "REFUSED" in r.stderr, r.stderr


def test_p0_limitation_is_stated_not_hidden(tmp_path):
    # The approvals table is the Phase-2 approvals migration (009) — never a
    # literal 008. The script must SAY the trailer is unresolved rather than
    # imply it checked a row.
    r = _check(tmp_path, ["MISSION.md"], "docs: x\n\nApproved-Protected-Path: ap-7f3a91\n")
    assert "not resolved" in r.stderr and "009" in r.stderr
    src = SCRIPT.read_text(encoding="utf-8")
    assert "migration 008" not in src and "pipenv run" not in src
    # The break-glass pointer is honest: --no-verify, documented in the runbook
    # (skills/god/SKILL.md documents PROD's pre-commit bypass, not this hook).
    assert "god/SKILL.md documents the bypass" not in src
    assert "--no-verify" in src and "runbook" in src
