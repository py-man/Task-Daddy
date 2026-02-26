from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
  return datetime.now(timezone.utc)


class Base(DeclarativeBase):
  pass


class User(Base):
  __tablename__ = "users"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
  name: Mapped[str] = mapped_column(String, nullable=False)
  password_hash: Mapped[str] = mapped_column(String, nullable=False)
  role: Mapped[str] = mapped_column(String, nullable=False)
  avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
  timezone: Mapped[str | None] = mapped_column(String, nullable=True)
  jira_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
  notification_prefs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
  quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  quiet_hours_start: Mapped[str | None] = mapped_column(String, nullable=True)
  quiet_hours_end: Mapped[str | None] = mapped_column(String, nullable=True)
  active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
  login_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
  mfa_recovery_codes_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Session(Base):
  __tablename__ = "sessions"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
  mfa_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  created_ip: Mapped[str | None] = mapped_column(String, nullable=True)
  user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MfaTrustedDevice(Base):
  __tablename__ = "mfa_trusted_devices"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
  token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
  created_ip: Mapped[str | None] = mapped_column(String, nullable=True)
  user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(Base):
  __tablename__ = "password_reset_tokens"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
  token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
  request_ip: Mapped[str | None] = mapped_column(String, nullable=True)
  used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ApiToken(Base):
  __tablename__ = "api_tokens"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
  name: Mapped[str] = mapped_column(String, nullable=False)
  token_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
  token_hint: Mapped[str] = mapped_column(String, nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Board(Base):
  __tablename__ = "boards"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  name: Mapped[str] = mapped_column(String, nullable=False)
  name_key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
  owner_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class BoardMember(Base):
  __tablename__ = "board_members"
  __table_args__ = (UniqueConstraint("board_id", "user_id", name="ux_board_member_board_user"),)

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False)
  user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
  role: Mapped[str] = mapped_column(String, nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BoardTaskType(Base):
  __tablename__ = "board_task_types"
  __table_args__ = (UniqueConstraint("board_id", "key", name="ux_board_task_types_board_key"),)

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False, index=True)
  key: Mapped[str] = mapped_column(String, nullable=False)
  name: Mapped[str] = mapped_column(String, nullable=False)
  color: Mapped[str | None] = mapped_column(String, nullable=True)
  enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
  position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class BoardTaskPriority(Base):
  __tablename__ = "board_task_priorities"
  __table_args__ = (UniqueConstraint("board_id", "key", name="ux_board_task_priorities_board_key"),)

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False, index=True)
  key: Mapped[str] = mapped_column(String, nullable=False)
  name: Mapped[str] = mapped_column(String, nullable=False)
  rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  color: Mapped[str | None] = mapped_column(String, nullable=True)
  enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Lane(Base):
  __tablename__ = "lanes"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False)
  name: Mapped[str] = mapped_column(String, nullable=False)
  state_key: Mapped[str] = mapped_column(String, nullable=False)
  type: Mapped[str] = mapped_column(String, nullable=False)
  wip_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
  position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Task(Base):
  __tablename__ = "tasks"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False)
  lane_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("lanes.id"), nullable=False)
  state_key: Mapped[str] = mapped_column(String, nullable=False)
  title: Mapped[str] = mapped_column(String, nullable=False)
  description: Mapped[str] = mapped_column(Text, nullable=False, default="")
  owner_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
  priority: Mapped[str] = mapped_column(String, nullable=False, default="P2")
  type: Mapped[str] = mapped_column(String, nullable=False, default="Feature")
  tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
  due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  estimate_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
  blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
  jira_key: Mapped[str | None] = mapped_column(String, nullable=True)
  jira_url: Mapped[str | None] = mapped_column(String, nullable=True)
  jira_connection_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("jira_connections.id"), nullable=True)
  jira_sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  jira_project_key: Mapped[str | None] = mapped_column(String, nullable=True)
  jira_issue_type: Mapped[str | None] = mapped_column(String, nullable=True)
  jira_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  jira_last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  openproject_work_package_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
  openproject_url: Mapped[str | None] = mapped_column(String, nullable=True)
  openproject_connection_id: Mapped[str | None] = mapped_column(
    UUID(as_uuid=False), ForeignKey("openproject_connections.id"), nullable=True
  )
  openproject_sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  openproject_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  openproject_last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class TaskImportKey(Base):
  __tablename__ = "task_import_keys"
  __table_args__ = (UniqueConstraint("board_id", "key", name="ux_task_import_board_key"),)

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False, index=True)
  key: Mapped[str] = mapped_column(Text, nullable=False)
  task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TaskDependency(Base):
  __tablename__ = "task_dependencies"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False)
  depends_on_task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Comment(Base):
  __tablename__ = "comments"
  __table_args__ = (UniqueConstraint("task_id", "source", "source_id", name="ux_comments_task_source_source_id"),)

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False)
  author_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
  body: Mapped[str] = mapped_column(Text, nullable=False)
  source: Mapped[str] = mapped_column(String, nullable=False, default="app")
  source_id: Mapped[str | None] = mapped_column(String, nullable=True)
  source_author: Mapped[str | None] = mapped_column(String, nullable=True)
  source_url: Mapped[str | None] = mapped_column(String, nullable=True)
  jira_comment_id: Mapped[str | None] = mapped_column(String, nullable=True)
  jira_exported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChecklistItem(Base):
  __tablename__ = "checklist_items"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False)
  text: Mapped[str] = mapped_column(Text, nullable=False)
  done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Attachment(Base):
  __tablename__ = "attachments"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False)
  filename: Mapped[str] = mapped_column(String, nullable=False)
  mime: Mapped[str] = mapped_column(String, nullable=False)
  size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
  path: Mapped[str] = mapped_column(String, nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditEvent(Base):
  __tablename__ = "audit_events"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=True)
  task_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=True)
  actor_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
  event_type: Mapped[str] = mapped_column(String, nullable=False)
  entity_type: Mapped[str] = mapped_column(String, nullable=False)
  entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
  payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class JiraConnection(Base):
  __tablename__ = "jira_connections"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  name: Mapped[str | None] = mapped_column(String, nullable=True)
  base_url: Mapped[str] = mapped_column(String, nullable=False)
  email: Mapped[str | None] = mapped_column(String, nullable=True)
  token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
  default_assignee_account_id: Mapped[str | None] = mapped_column(String, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class OpenProjectConnection(Base):
  __tablename__ = "openproject_connections"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  name: Mapped[str] = mapped_column(String, nullable=False, default="OpenProject")
  base_url: Mapped[str] = mapped_column(String, nullable=False)
  api_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
  project_identifier: Mapped[str | None] = mapped_column(String, nullable=True)
  enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
  token_hint: Mapped[str] = mapped_column(String, nullable=False, default="")
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class JiraSyncProfile(Base):
  __tablename__ = "jira_sync_profiles"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False)
  connection_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jira_connections.id"), nullable=False)
  jql: Mapped[str] = mapped_column(Text, nullable=False)
  status_to_state_key: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
  priority_map: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
  type_map: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
  conflict_policy: Mapped[str] = mapped_column(String, nullable=False, default="jiraWins")
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class SyncRun(Base):
  __tablename__ = "sync_runs"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False)
  profile_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("jira_sync_profiles.id"), nullable=False)
  status: Mapped[str] = mapped_column(String, nullable=False, default="success")
  started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  log: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
  error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class WebhookSecret(Base):
  __tablename__ = "webhook_secrets"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  source: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
  enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
  bearer_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
  token_hint: Mapped[str] = mapped_column(String, nullable=False, default="")
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class InAppNotification(Base):
  __tablename__ = "in_app_notifications"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
  level: Mapped[str] = mapped_column(String, nullable=False, default="info")  # info | warn | error | ok
  title: Mapped[str] = mapped_column(String, nullable=False)
  body: Mapped[str] = mapped_column(Text, nullable=False)
  event_type: Mapped[str | None] = mapped_column(String, nullable=True)
  taxonomy: Mapped[str] = mapped_column(String, nullable=False, default="informational")
  entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
  entity_id: Mapped[str | None] = mapped_column(String, nullable=True)
  dedupe_key: Mapped[str | None] = mapped_column(String, nullable=True)
  burst_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
  last_occurrence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class InboundWebhookEvent(Base):
  __tablename__ = "inbound_webhook_events"
  __table_args__ = (
    UniqueConstraint("source", "idempotency_key", name="ux_inbound_webhook_source_idempotency"),
  )

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  source: Mapped[str] = mapped_column(String, nullable=False, index=True)
  idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
  headers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
  body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
  received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
  processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
  error: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationDestination(Base):
  __tablename__ = "notification_destinations"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  provider: Mapped[str] = mapped_column(String, nullable=False)  # local | pushover
  name: Mapped[str] = mapped_column(String, nullable=False, default="Default")
  enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
  config_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
  token_hint: Mapped[str] = mapped_column(String, nullable=False, default="")
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class BackupPolicy(Base):
  __tablename__ = "backup_policies"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
  min_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
  max_backups: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
  max_total_size_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=2048)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class TaskReminder(Base):
  __tablename__ = "task_reminders"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
  task_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tasks.id"), nullable=False, index=True)
  board_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("boards.id"), nullable=False, index=True)
  created_by_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
  recipient_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
  scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
  note: Mapped[str] = mapped_column(Text, nullable=False, default="")
  channels: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=lambda: ["inapp"])
  status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending|sending|sent|error|canceled
  attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
  last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
