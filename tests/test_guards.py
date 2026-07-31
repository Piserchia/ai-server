"""
Guards (SDK-native isolation) — pure predicates + hook factory.

These replace the container lane's OS isolation with PreToolUse denials, so
the tests are the enforcement contract for INV-17: if a case here weakens,
workspace-tier sessions gain host access.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.runner import guards


# ── write_target_violation ──────────────────────────────────────────────────


class TestWriteTargetViolation:
    def _ws(self, tmp_path: Path) -> Path:
        ws = tmp_path / "ws"
        ws.mkdir()
        return ws

    def test_write_inside_workspace_allowed(self, tmp_path):
        ws = self._ws(tmp_path)
        assert guards.write_target_violation(
            "Write", {"file_path": str(ws / "a.py")}, ws, extra_allowed=[]
        ) is None

    def test_write_in_nested_subdir_allowed(self, tmp_path):
        ws = self._ws(tmp_path)
        assert guards.write_target_violation(
            "Edit", {"file_path": str(ws / "src" / "deep" / "b.py")}, ws, extra_allowed=[]
        ) is None

    def test_write_outside_workspace_denied(self, tmp_path):
        ws = self._ws(tmp_path)
        reason = guards.write_target_violation(
            "Write", {"file_path": "/opt/escape.py"}, ws, extra_allowed=[]
        )
        assert reason is not None and "outside the job workspace" in reason

    def test_relative_path_anchors_to_workspace(self, tmp_path):
        ws = self._ws(tmp_path)
        assert guards.write_target_violation(
            "Write", {"file_path": "sub/rel.py"}, ws, extra_allowed=[]
        ) is None

    def test_dotdot_traversal_denied(self, tmp_path):
        ws = self._ws(tmp_path)
        reason = guards.write_target_violation(
            "Write", {"file_path": str(ws / ".." / "escape.py")}, ws, extra_allowed=[]
        )
        assert reason is not None

    def test_scratch_dir_allowed_when_listed(self, tmp_path):
        ws = self._ws(tmp_path)
        scratch = tmp_path / "scratch"
        scratch.mkdir()
        assert guards.write_target_violation(
            "Write", {"file_path": str(scratch / "notes.md")}, ws,
            extra_allowed=[scratch],
        ) is None

    def test_notebook_path_key_checked(self, tmp_path):
        ws = self._ws(tmp_path)
        reason = guards.write_target_violation(
            "NotebookEdit", {"notebook_path": "/opt/x.ipynb"}, ws, extra_allowed=[]
        )
        assert reason is not None

    def test_non_write_tool_ignored(self, tmp_path):
        ws = self._ws(tmp_path)
        assert guards.write_target_violation(
            "Read", {"file_path": "/opt/anything"}, ws, extra_allowed=[]
        ) is None

    def test_missing_path_ignored(self, tmp_path):
        ws = self._ws(tmp_path)
        assert guards.write_target_violation("Write", {}, ws, extra_allowed=[]) is None

    def test_default_scratch_covers_tmp(self, tmp_path):
        ws = self._ws(tmp_path)
        # extra_allowed=None → real scratch dirs (/tmp et al.) are permitted.
        assert guards.write_target_violation(
            "Write", {"file_path": "/tmp/scratch-note.md"}, ws, extra_allowed=None
        ) is None


# ── bash_violation ──────────────────────────────────────────────────────────


WS = Path("/protected/root/volumes/workspaces/abc12345-repo")
ROOTS = [Path("/protected/root")]


class TestBashViolation:
    def test_sudo_denied(self):
        assert guards.bash_violation("sudo rm -rf /", WS, ROOTS)

    def test_launchctl_denied(self):
        assert guards.bash_violation("launchctl bootout gui/501/com.assistant.runner", WS, ROOTS)

    def test_keychain_read_denied(self):
        assert guards.bash_violation(
            'security find-generic-password -s "Claude"', WS, ROOTS)

    def test_force_push_denied(self):
        assert guards.bash_violation("git push --force origin main", WS, ROOTS)
        assert guards.bash_violation("git push -f", WS, ROOTS)
        assert guards.bash_violation("git push origin main --force-with-lease", WS, ROOTS)

    def test_normal_push_allowed(self):
        assert guards.bash_violation("git push origin HEAD:server-patch/fix", WS, ROOTS) is None

    def test_process_kills_denied(self):
        assert guards.bash_violation("killall Python", WS, ROOTS)
        assert guards.bash_violation("pkill -f runner", WS, ROOTS)

    def test_crontab_denied(self):
        assert guards.bash_violation("crontab -e", WS, ROOTS)

    def test_api_key_injection_denied(self):
        assert guards.bash_violation("export ANTHROPIC_API_KEY=sk-x", WS, ROOTS)
        assert guards.bash_violation("ANTHROPIC_API_KEY=sk-x python x.py", WS, ROOTS)

    def test_rm_on_protected_root_denied(self):
        assert guards.bash_violation("rm -rf /protected/root/src", WS, ROOTS)

    def test_home_var_spelling_of_root_denied(self):
        # $HOME / ${HOME} are the spellings a session actually emits for a
        # home-relative root (regression: these bypassed the literal matcher).
        home_root = Path.home() / ".ssh"
        assert guards.bash_violation("rm -rf $HOME/.ssh", WS, [home_root])
        assert guards.bash_violation("rm -rf ${HOME}/.ssh/id_rsa", WS, [home_root])

    def test_spaced_root_all_spellings_denied(self):
        # The production checkout path contains a space; a session may write
        # it quoted-absolute, backslash-escaped, or via $HOME.
        root = Path("/Users/x/Library/Application Support/ai-server")
        roots = [root]
        for cmd in (
            'rm -rf "/Users/x/Library/Application Support/ai-server/src"',
            r"rm -rf /Users/x/Library/Application\ Support/ai-server/src",
        ):
            assert guards.bash_violation(cmd, WS, roots), cmd

    def test_git_reset_hard_on_protected_root_denied(self):
        # The 2026-07-09 single-writer incident class.
        assert guards.bash_violation("git -C /protected/root reset --hard origin/main", WS, ROOTS)
        assert guards.bash_violation("git -C /protected/root checkout -- src/", WS, ROOTS)
        assert guards.bash_violation("git -C /protected/root clean -fd", WS, ROOTS)

    def test_in_workspace_git_reset_allowed(self):
        # Same destructive git, but against the clone → fine (masked to «WS»).
        assert guards.bash_violation(f"git -C {WS} reset --hard HEAD", WS, ROOTS) is None
        assert guards.bash_violation("git reset --hard HEAD~1", WS, ROOTS) is None

    def test_git_commit_in_protected_root_denied(self):
        # Pull-only runtime clone lives under server_root (a protected root);
        # committing there via absolute path is the single-writer violation.
        assert guards.bash_violation("git -C /protected/root commit -m x", WS, ROOTS)
        assert guards.bash_violation(
            "cd /protected/root/projects/atlas && git add -A && git commit -m y", WS, ROOTS)

    def test_in_workspace_git_commit_allowed(self):
        # The normal workspace flow: commit with no protected-root reference.
        assert guards.bash_violation("git add -A && git commit -m 'work'", WS, ROOTS) is None
        assert guards.bash_violation(f"cd {WS} && git add -A && git commit -m z", WS, ROOTS) is None

    def test_refspec_force_push_denied(self):
        assert guards.bash_violation("git push origin +main:main", WS, ROOTS)

    def test_bare_kill_denied(self):
        assert guards.bash_violation("kill 8123", WS, ROOTS)
        assert guards.bash_violation("kill $(pgrep -f runner)", WS, ROOTS)

    def test_find_delete_on_protected_root_denied(self):
        assert guards.bash_violation(
            "find /protected/root -name '*.py' -delete", WS, ROOTS)

    def test_skill_word_not_a_false_kill(self):
        # "skill" contains "kill" — must not trip the process-kill guard.
        assert guards.bash_violation("cat skills/app-patch/SKILL.md", WS, ROOTS) is None

    def test_redirect_into_protected_root_denied(self):
        assert guards.bash_violation("echo hacked > /protected/root/.env", WS, ROOTS)

    def test_sed_inplace_on_protected_root_denied(self):
        assert guards.bash_violation(
            "sed -i '' 's/a/b/' /protected/root/src/config.py", WS, ROOTS)

    def test_readonly_reference_to_protected_root_allowed(self):
        assert guards.bash_violation("grep -rn quota /protected/root/src", WS, ROOTS) is None
        assert guards.bash_violation("git -C /protected/root log --oneline", WS, ROOTS) is None

    def test_workspace_under_protected_root_is_masked(self):
        # Clones live UNDER server_root — mutating inside the clone is fine.
        assert guards.bash_violation(f"rm -rf {WS}/build", WS, ROOTS) is None
        assert guards.bash_violation(f"echo ok > {WS}/out.txt", WS, ROOTS) is None

    def test_path_boundary_no_false_positive(self):
        assert guards.bash_violation("rm -rf /protected/root-backup/x", WS, ROOTS) is None

    def test_tilde_form_of_home_root_denied(self):
        home_root = Path.home() / ".claude"
        assert guards.bash_violation("rm -rf ~/.claude", WS, [home_root])

    def test_benign_commands_allowed(self):
        for cmd in (
            "pipenv run pytest tests/ -v",
            "git status && git diff",
            "python -m src.runner.main --help",
            "ls -la && cat README.md",
        ):
            assert guards.bash_violation(cmd, WS, ROOTS) is None, cmd

    def test_empty_command_allowed(self):
        assert guards.bash_violation("", WS, ROOTS) is None


# ── hook factory ────────────────────────────────────────────────────────────


class TestGuardHooks:
    def test_structure(self, tmp_path):
        hooks = guards.make_guard_hooks("job-1", tmp_path)
        assert set(hooks) == {"PreToolUse"}
        matchers = hooks["PreToolUse"]
        assert len(matchers) == 2
        assert matchers[0].matcher == "|".join(guards.FILE_WRITE_TOOLS)
        assert matchers[1].matcher == "Bash"

    async def test_file_hook_denies_and_audits(self, tmp_path, monkeypatch):
        events: list[tuple] = []
        monkeypatch.setattr(guards.audit_log, "append",
                            lambda job_id, kind, **kw: events.append((job_id, kind, kw)))
        ws = tmp_path / "ws"
        ws.mkdir()
        hooks = guards.make_guard_hooks("job-2", ws)
        file_hook = hooks["PreToolUse"][0].hooks[0]

        out = await file_hook(
            {"tool_name": "Write", "tool_input": {"file_path": "/opt/escape.py"}},
            "tu-1", None,
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert events and events[0][1] == "guard_denied"

    async def test_file_hook_allows_workspace_write(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        hooks = guards.make_guard_hooks("job-3", ws)
        file_hook = hooks["PreToolUse"][0].hooks[0]
        out = await file_hook(
            {"tool_name": "Write", "tool_input": {"file_path": str(ws / "ok.py")}},
            "tu-2", None,
        )
        assert out == {}

    async def test_bash_hook_denies_sudo(self, tmp_path, monkeypatch):
        events: list[tuple] = []
        monkeypatch.setattr(guards.audit_log, "append",
                            lambda job_id, kind, **kw: events.append((job_id, kind, kw)))
        hooks = guards.make_guard_hooks("job-4", tmp_path)
        bash_hook = hooks["PreToolUse"][1].hooks[0]
        out = await bash_hook(
            {"tool_name": "Bash", "tool_input": {"command": "sudo reboot"}},
            "tu-3", None,
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert events[0][2]["command"] == "sudo reboot"

    async def test_bash_hook_allows_benign(self, tmp_path):
        hooks = guards.make_guard_hooks("job-5", tmp_path)
        bash_hook = hooks["PreToolUse"][1].hooks[0]
        out = await bash_hook(
            {"tool_name": "Bash", "tool_input": {"command": "pytest -q"}},
            "tu-4", None,
        )
        assert out == {}


# ── read-only profile: readonly_file_violation ──────────────────────────────


class TestReadonlyFileViolation:
    @pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
    def test_file_mutation_tools_always_denied(self, tool):
        reason = guards.readonly_file_violation(tool)
        assert reason is not None and "read-only" in reason

    @pytest.mark.parametrize(
        "tool", ["Read", "Glob", "Grep", "Bash", "Task", "WebFetch", "WebSearch"])
    def test_non_mutating_tools_ignored(self, tool):
        assert guards.readonly_file_violation(tool) is None


# ── read-only profile: readonly_bash_violation ──────────────────────────────

# Deny matrix: every mutation class the profile promises to stop.
RO_DENY = [
    # output redirection / tee
    "echo hacked > /tmp/x",
    "echo x >> notes.md",
    "git log --oneline | tee /tmp/out.txt",
    'psql assistant -c "SELECT * FROM jobs" > /tmp/dump.txt',
    # sed -i and file mutators
    "sed -i '' 's/a/b/' src/config.py",
    "rm -rf volumes/workspaces/old",
    "mv a.txt b.txt",
    "cp .env /tmp/steal",
    "mkdir -p /tmp/scratch",
    "touch marker",
    "chmod +x run.sh",
    "chown me:staff f",
    "ln -s /etc/passwd link",
    "find volumes/ -name '*.log' -delete",
    # git mutators (fetch is the sanctioned exception — see allow matrix)
    "git push origin main",
    "git commit -m 'x'",
    "git add -A",
    "git checkout -- src/",
    "git reset --hard origin/main",
    "git merge origin/main",
    "git pull --rebase origin main",
    "git rebase main",
    "git stash",
    "git cherry-pick abc1234",
    "git fetch origin && git merge origin/main",
    # psql write verbs — word-boundary, case-insensitive
    "psql assistant -c \"UPDATE jobs SET status='failed' WHERE id='x'\"",
    "psql assistant -c \"update jobs set status='x'\"",
    "psql assistant -c \"INSERT INTO jobs (kind) VALUES ('x')\"",
    'psql assistant -c "DELETE FROM proposals"',
    'psql assistant -c "drop table jobs"',
    'psql assistant -c "ALTER TABLE jobs ADD COLUMN x int"',
    'psql assistant -c "CREATE TABLE evil (id int)"',
    'psql assistant -c "TRUNCATE jobs"',
    'psql assistant -c "GRANT ALL ON jobs TO evil"',
    'psql assistant -c "SELECT 1; DELETE FROM jobs;"',
    # redis-cli mutators
    "redis-cli set quota:paused_until 0",
    "redis-cli del jobs:queue",
    "redis-cli rpush jobs:queue payload",
    "redis-cli lpush jobs:queue payload",
    "redis-cli LPOP jobs:queue",
    "redis-cli flushall",
    "redis-cli flushdb",
    "redis-cli expire quota:paused_until 1",
    # launchctl service mutation
    "launchctl kickstart -k gui/501/com.assistant.runner",
    "launchctl bootout gui/501/com.assistant.web",
    "launchctl stop com.assistant.runner",
    "launchctl start com.assistant.runner",
    "launchctl kill SIGTERM gui/501/com.assistant.runner",
    # migrations / db admin
    "alembic upgrade head",
    "pipenv run alembic downgrade -1",
    "alembic revision -m 'x'",
    "dbmate up",
    "dropdb assistant",
    # package/environment managers
    "pipenv install requests",
    "pipenv sync",
    "pipenv lock",
    "pip install httpx",
    "pip3 uninstall httpx",
    "npm install left-pad",
    "npm ci",
    "npx install thing",
    "brew install jq",
    "brew services restart redis",
    # hard denials
    "sudo rm -rf /",
    "kill 8123",
    "pkill -f runner",
    "crontab -e",
    "security find-generic-password -s Claude",
    "export ANTHROPIC_API_KEY=sk-x",
]

# Allow matrix: the REAL inspection vocabulary from the oversight skill bodies
# (managers, CEO, deploy-director, review-and-improve). A false positive here
# breaks a live skill — these are the regression net for that.
RO_ALLOW = [
    # SQL — comparison `>` inside quotes, verb-like column/skill names
    ("psql assistant -c \"SELECT resolved_skill, status FROM jobs "
     "WHERE created_at > NOW() - INTERVAL '14 days' "
     "ORDER BY created_at DESC LIMIT 40;\""),
    ("psql assistant -c \"SELECT resolved_skill, status FROM jobs "
     "WHERE resolved_skill IN ('new-project','app-patch','project-evaluate',"
     "'project-redeploy','project-update-poll','code-review','_evaluate');\""),
    ("psql assistant -c \"SELECT count(*), date_trunc('day', created_at) "
     "FROM jobs GROUP BY 2 ORDER BY 2 DESC LIMIT 7;\""),
    ("psql assistant -c \"SELECT name, cron_expression, paused FROM schedules "
     "WHERE replace(job_kind,'_','-') IN ('research-report','research-deep',"
     "'idea-generation');\""),
    ("psql assistant -c \"SELECT LEFT(id::text,8), outcome, change_type, "
     "LEFT(target_file,60), proposed_at FROM proposals "
     "WHERE applied_at IS NULL ORDER BY proposed_at LIMIT 20;\""),
    'psql assistant -c "\\dt"',
    'psql assistant -c "\\d jobs"',
    'psql assistant -c "SELECT 1;"',
    # git inspection + the sanctioned refs-only fetch
    "git log --oneline HEAD..origin/main",
    'git -C "$HOME/Library/Application Support/ai-server" fetch origin',
    "git status --short --branch",
    "git rev-parse HEAD",
    "git diff --stat HEAD..origin/main",
    "git diff --name-only HEAD..origin/main",
    "git -C projects/atlas log --oneline '@{u}..HEAD' 2>/dev/null | head -5",
    "git -C projects/research remote -v 2>/dev/null | head -1",
    "git -C \"$p\" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1",
    # the delivery-manager dev-repo coherence loop, verbatim shape
    ("for p in projects/*/; do if git -C \"$p\" rev-parse --abbrev-ref '@{u}' "
     ">/dev/null 2>&1; then git -C \"$p\" log --oneline '@{u}..HEAD' "
     "| sed \"s|^|$p ahead: |\" | head -3; else echo \"$p NO-UPSTREAM\"; fi; done"),
    # plain reads (incl. stderr-to-/dev/null, which must NOT trip redirection)
    "grep -rn quota src/",
    "grep -h escalation_spawned volumes/audit_log/*.jsonl 2>/dev/null | tail -20",
    "grep -n 'ANTHROPIC_API_KEY' projects/atlas/manifest.yml 2>/dev/null",
    "grep -l '^delivery:' projects/*/manifest.yml 2>/dev/null",
    "ls -la volumes/logs/",
    "ls -lt projects/research/ 2>/dev/null | head -15",
    "cat volumes/audit_log/abc12345.summary.md",
    "tail -5 projects/ideas/history.jsonl 2>/dev/null",
    "curl -so /dev/null -w '%{http_code}' http://localhost:8080/health",
    "df -h .",
    # redis / launchctl / alembic read-only forms
    "redis-cli get quota:paused_until",
    "redis-cli llen jobs:queue",
    "redis-cli lrange jobs:queue 0 5",
    "redis-cli ping",
    "launchctl list | grep com.assistant",
    "pipenv run alembic current",
    "pipenv run alembic heads",
    "pipenv run python scripts/lint_docs.py",
    "echo \"$p NO-UPSTREAM\"",
]


class TestReadonlyBashViolation:
    @pytest.mark.parametrize("cmd", RO_DENY, ids=lambda c: c[:48])
    def test_denied(self, cmd):
        assert guards.readonly_bash_violation(cmd) is not None, f"should DENY: {cmd}"

    @pytest.mark.parametrize("cmd", RO_ALLOW, ids=lambda c: c[:48])
    def test_allowed(self, cmd):
        assert guards.readonly_bash_violation(cmd) is None, f"should ALLOW: {cmd}"

    def test_empty_command_allowed(self):
        assert guards.readonly_bash_violation("") is None

    def test_deny_reason_names_the_profile(self):
        reason = guards.readonly_bash_violation("git push origin main")
        assert reason is not None and "read-only" in reason


# ── read-only profile: hook factory ─────────────────────────────────────────


class TestReadonlyGuardHooks:
    def test_structure(self):
        hooks = guards.make_readonly_guard_hooks("job-r1")
        assert set(hooks) == {"PreToolUse"}
        matchers = hooks["PreToolUse"]
        assert len(matchers) == 3
        assert matchers[0].matcher == "|".join(guards.FILE_WRITE_TOOLS)
        assert matchers[1].matcher == "Bash"
        assert matchers[2].matcher == f".*{guards.RESTART_TOOL_SUFFIX}"

    def test_restart_matcher_matches_mcp_name_under_both_regex_semantics(self):
        # The SDK treats matcher strings as regex (the existing "A|B" matcher
        # relies on it); the suffix pattern must hold under fullmatch AND search.
        pattern = f".*{guards.RESTART_TOOL_SUFFIX}"
        assert re.fullmatch(pattern, "mcp__projects__restart_project")
        assert re.search(pattern, "mcp__projects__restart_project")

    def test_enqueue_job_never_matched(self):
        # Dispatch is the tier's sanctioned state change — no matcher may
        # claim the dispatch MCP tool under either regex semantics.
        hooks = guards.make_readonly_guard_hooks("job-r2")
        name = "mcp__dispatch__enqueue_job"
        for m in hooks["PreToolUse"]:
            assert not re.fullmatch(m.matcher, name), m.matcher
            assert not re.search(m.matcher, name), m.matcher

    async def test_file_hook_denies_even_tmp_and_audits_profile(self, monkeypatch):
        events: list[tuple] = []
        monkeypatch.setattr(guards.audit_log, "append",
                            lambda job_id, kind, **kw: events.append((job_id, kind, kw)))
        hooks = guards.make_readonly_guard_hooks("job-r3")
        file_hook = hooks["PreToolUse"][0].hooks[0]
        # /tmp is allowed for the workspace profile — the read-only profile
        # has NO path exceptions.
        out = await file_hook(
            {"tool_name": "Write", "tool_input": {"file_path": "/tmp/scratch.md"}},
            "tu-r1", None,
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert events[0][1] == "guard_denied"
        assert events[0][2]["profile"] == "read-only"

    async def test_bash_hook_allows_select(self):
        hooks = guards.make_readonly_guard_hooks("job-r4")
        bash_hook = hooks["PreToolUse"][1].hooks[0]
        out = await bash_hook(
            {"tool_name": "Bash",
             "tool_input": {"command": 'psql assistant -c "SELECT 1;"'}},
            "tu-r2", None,
        )
        assert out == {}

    async def test_bash_hook_denies_push_and_audits_profile(self, monkeypatch):
        events: list[tuple] = []
        monkeypatch.setattr(guards.audit_log, "append",
                            lambda job_id, kind, **kw: events.append((job_id, kind, kw)))
        hooks = guards.make_readonly_guard_hooks("job-r5")
        bash_hook = hooks["PreToolUse"][1].hooks[0]
        out = await bash_hook(
            {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}},
            "tu-r3", None,
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert events[0][2]["profile"] == "read-only"
        assert events[0][2]["command"] == "git push origin main"

    async def test_restart_hook_denies_by_suffix_and_audits(self, monkeypatch):
        events: list[tuple] = []
        monkeypatch.setattr(guards.audit_log, "append",
                            lambda job_id, kind, **kw: events.append((job_id, kind, kw)))
        hooks = guards.make_readonly_guard_hooks("job-r6")
        restart_hook = hooks["PreToolUse"][2].hooks[0]
        out = await restart_hook(
            {"tool_name": "mcp__projects__restart_project",
             "tool_input": {"slug": "atlas"}},
            "tu-r4", None,
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert events[0][1] == "guard_denied"
        assert events[0][2]["profile"] == "read-only"

    async def test_restart_hook_ignores_other_projects_tools(self):
        # The hook re-checks the suffix, so even if the matcher were broader
        # than intended it can never deny an unrelated tool.
        hooks = guards.make_readonly_guard_hooks("job-r7")
        restart_hook = hooks["PreToolUse"][2].hooks[0]
        out = await restart_hook(
            {"tool_name": "mcp__projects__list_projects", "tool_input": {}},
            "tu-r5", None,
        )
        assert out == {}
