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

    # Paths
    server_root: Path = Path.home() / "Library" / "Application Support" / "assistant"

    # Runner
    # 4 is safe now that code-writing skills run in per-job workspace clones
    # (P1) — no shared-checkout collisions. Quota auto-pause still guards the
    # subscription budget.
    max_concurrent_jobs: int = 4
    session_timeout_seconds: int = 1800

    # Containers (P1) — the high-risk isolation lane. Empty = disabled
    # (container-tier skills silently downgrade to workspace isolation).
    # Runtime is the CLI name: "docker" works with colima / Docker Desktop /
    # OrbStack. Token comes from `claude setup-token` (subscription auth —
    # NEVER an API key).
    container_runtime: str = ""
    agent_image: str = "ai-server-agent:latest"
    container_memory: str = "4g"
    container_cpus: str = "2"
    claude_code_oauth_token: str = ""
    # GET /health returns 503 if the runner heartbeat is older than this. The
    # runner writes it every loop (≤2s normally, ~30s during a quota pause), so
    # 90s tolerates a pause without false alarms.
    runner_heartbeat_stale_seconds: int = 90

    # Quota
    quota_pause_minutes: int = 60

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
