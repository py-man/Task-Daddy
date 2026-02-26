from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_file=".env", extra="ignore")

  database_url: str = "postgresql+asyncpg://neonlanes:neonlanes@db:5432/neonlanes"
  app_secret: str = "dev-secret-change-me"
  fernet_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
  app_version: str = "v2026-02-26+r3-hardening"
  build_sha: str = "dev"

  cookie_secure: bool = False
  cookie_domain: str | None = None
  force_logout_on_start: bool = False

  rate_limit_login_ip_per_minute: int = 60
  rate_limit_login_email_per_minute: int = 20
  rate_limit_password_reset_ip_per_minute: int = 10
  rate_limit_password_reset_email_per_minute: int = 5
  mfa_trusted_device_ttl_days: int = 30

  cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://0.0.0.0:3000"
  cors_origin_regex: str = r"^http://(localhost|127\.0\.0\.1|0\.0\.0\.0):3000$"
  trusted_hosts: str = "localhost,127.0.0.1,0.0.0.0,api,web"

  ai_provider: str = "local"  # local | openai
  openai_api_key: str | None = None
  openai_base_url: str = "https://api.openai.com/v1"

  jira_user_agent: str = "Task-Daddy/0.1 (local)"
  jira_base_url: str | None = None
  jira_email: str | None = None
  jira_token: str | None = None
  jira_default_assignee_account_id: str | None = None
  jira_auto_sync_enabled: bool = False
  jira_auto_sync_interval_seconds: int = 300
  redis_url: str | None = "redis://redis:6379/0"

  backup_dir: str = "data/backups"
  backup_auto_enabled: bool = True
  backup_auto_time_utc: str = "03:00"  # HH:MM
  backup_retention_days: int = 5
  backup_min_interval_minutes: int = 60
  backup_max_count: int = 30
  backup_max_total_size_mb: int = 2048

  max_attachment_bytes: int = 10 * 1024 * 1024

  def cors_origin_list(self) -> list[str]:
    return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

  def trusted_host_list(self) -> list[str]:
    return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]


settings = Settings()
