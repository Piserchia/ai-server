"""
Settings. One place; everything else imports `settings` from here.

Auth model: Claude subscription via bundled Claude Code CLI.
NO anthropic_api_key field — setting it would silently switch the SDK to
API billing. The bootstrap script actively unsets ANTHROPIC_API_KEY.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Models
    default_model: str = "claude-sonnet-4-6"
    # Utility model for the one-turn, fail-open classifiers (LLM router,
    # learning extractor). Was a hard-coded Haiku 4.5 pin until that model's
    # retirement window opened 2026-10-15 (T0, 2026-10-21).
    utility_model: str = "claude-sonnet-4-6"
    utility_effort: str = "low"

    # Providers (cross-vendor writer slice T1, 2026-10-21). Model ids are
    # `[provider/]model_id` resolved against the repo-root `models.yml`
    # (src/registry/models.py); bare ids are Anthropic. These switches are
    # the fail-closed gate: a provider absent from the CSV is refused before
    # any process starts. Flipping them is the owner's call (plan §7).
    router_providers_enabled: str = "anthropic"
    # Providers allowed on the `code-server` skill set (server-patch,
    # server-deploy, new-skill, deploy-director, *-redeploy) — D-A, default off.
    router_code_server_providers: str = "anthropic"
    # Codex CLI executor (T3): binary path ("" → shutil.which("codex") → the
    # ChatGPT.app bundle), CODEX_HOME for the login ("" → ~/.codex), and the
    # Seatbelt sandbox mode passed as `--sandbox`.
    codex_bin: str = ""
    codex_home: str = ""
    codex_sandbox_default: str = "workspace-write"
    # D-C read-side containment: when set (env CODEX_RUN_AS_USER), the
    # executor prefixes its argv with `sudo -n -u <user> --` (the sudoers
    # line is owner work). Unset by default — see plan §6 for the residual.
    codex_run_as_user: str = ""

    # Database
    postgres_dsn: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str = ""
    telegram_allowed_chat_ids: str = ""  # comma-separated

    # Web
    web_auth_token: str = ""
    web_port: int = 8080

    # Paths. The default MUST match the real prod install dir name
    # (`ai-server`); the previous `assistant` default was wrong and silently
    # repointed every volume path (audit_log/logs/projects/workspaces) at a
    # non-existent dir whenever SERVER_ROOT was unset (e.g. a subprocess env).
    server_root: Path = Path.home() / "Library" / "Application Support" / "ai-server"

    # Runner
    # 4 is safe now that code-writing skills run in per-job workspace clones
    # (P1) — no shared-checkout collisions. Quota auto-pause still guards the
    # subscription budget.
    max_concurrent_jobs: int = 4
    session_timeout_seconds: int = 1800

    # GET /health returns 503 if the runner heartbeat is older than this. The
    # runner writes it every loop (≤2s normally, ~30s during a quota pause), so
    # 90s tolerates a pause without false alarms.
    runner_heartbeat_stale_seconds: int = 90

    # Quota
    quota_pause_minutes: int = 60

    # Intent pipeline (P2/P3)
    # LLM routing fallback for asks the regex rules don't match (utility_model, 1 turn).
    llm_router_enabled: bool = True
    # Plans auto-approve: the plan is posted to Telegram with a Cancel button
    # and execution starts immediately. Set false to require explicit approval.
    plan_auto_approve: bool = True
    # After task_complete, run the _evaluate acceptance check; pass auto-closes
    # the task (evidence DM'd, Reopen button), fail re-opens with feedback.
    auto_evaluate: bool = True
    # Max evaluate→fix rounds before falling back to awaiting_user.
    max_eval_rounds: int = 2

    # Domain (Phase 3+)
    server_domain: str = ""

    @property
    def allowed_chat_ids(self) -> list[int]:
        if not self.telegram_allowed_chat_ids.strip():
            return []
        return [int(x.strip()) for x in self.telegram_allowed_chat_ids.split(",") if x.strip()]

    @property
    def audit_log_dir(self) -> Path:
        return self.server_root / "volumes" / "audit_log"

    @property
    def logs_dir(self) -> Path:
        return self.server_root / "volumes" / "logs"

    @property
    def projects_dir(self) -> Path:
        return self.server_root / "projects"

    @property
    def skills_dir(self) -> Path:
        return self.server_root / "skills"

    @property
    def workspaces_dir(self) -> Path:
        return self.server_root / "volumes" / "workspaces"

    @property
    def context_dir(self) -> Path:
        return self.server_root / ".context"


settings = Settings()  # type: ignore[call-arg]
