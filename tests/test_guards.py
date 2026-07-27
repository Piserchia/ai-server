"""
Guards (SDK-native isolation) — pure predicates + hook factory.

These replace the container lane's OS isolation with PreToolUse denials, so
the tests are the enforcement contract for INV-17: if a case here weakens,
workspace-tier sessions gain host access.
"""

from __future__ import annotations

from pathlib import Path

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
