"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "users",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("email", sa.String(), nullable=False),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("password_hash", sa.String(), nullable=False),
    sa.Column("role", sa.String(), nullable=False),
    sa.Column("avatar_url", sa.String(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_users_email", "users", ["email"], unique=True)

  op.create_table(
    "sessions",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)

  op.create_table(
    "boards",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("owner_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_boards_owner_id", "boards", ["owner_id"], unique=False)

  op.create_table(
    "board_members",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("board_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("role", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ux_board_members_board_user", "board_members", ["board_id", "user_id"], unique=True)

  op.create_table(
    "lanes",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("board_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("state_key", sa.String(), nullable=False),
    sa.Column("type", sa.String(), nullable=False),
    sa.Column("wip_limit", sa.Integer(), nullable=True),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ux_lanes_board_state_key", "lanes", ["board_id", "state_key"], unique=True)
  op.create_index("ix_lanes_board_pos", "lanes", ["board_id", "position"], unique=False)

  op.create_table(
    "tasks",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("board_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("lane_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("state_key", sa.String(), nullable=False),
    sa.Column("title", sa.String(), nullable=False),
    sa.Column("description", sa.Text(), nullable=False),
    sa.Column("owner_id", postgresql.UUID(as_uuid=False), nullable=True),
    sa.Column("priority", sa.String(), nullable=False),
    sa.Column("type", sa.String(), nullable=False),
    sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False),
    sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
    sa.Column("estimate_minutes", sa.Integer(), nullable=True),
    sa.Column("blocked", sa.Boolean(), nullable=False),
    sa.Column("blocked_reason", sa.Text(), nullable=True),
    sa.Column("jira_key", sa.String(), nullable=True),
    sa.Column("jira_url", sa.String(), nullable=True),
    sa.Column("jira_updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("jira_last_sync_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("order_index", sa.Integer(), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_tasks_board_lane_order", "tasks", ["board_id", "lane_id", "order_index"], unique=False)
  op.create_index("ix_tasks_board_due", "tasks", ["board_id", "due_date"], unique=False)
  op.create_index("ix_tasks_jira_key", "tasks", ["jira_key"], unique=False)

  op.create_table(
    "task_dependencies",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ux_task_dep", "task_dependencies", ["task_id", "depends_on_task_id"], unique=True)

  op.create_table(
    "comments",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("author_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_comments_task_created", "comments", ["task_id", "created_at"], unique=False)

  op.create_table(
    "checklist_items",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("text", sa.Text(), nullable=False),
    sa.Column("done", sa.Boolean(), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_checklist_task_pos", "checklist_items", ["task_id", "position"], unique=False)

  op.create_table(
    "attachments",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("filename", sa.String(), nullable=False),
    sa.Column("mime", sa.String(), nullable=False),
    sa.Column("size_bytes", sa.Integer(), nullable=False),
    sa.Column("path", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_attachments_task_created", "attachments", ["task_id", "created_at"], unique=False)

  op.create_table(
    "audit_events",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("board_id", postgresql.UUID(as_uuid=False), nullable=True),
    sa.Column("task_id", postgresql.UUID(as_uuid=False), nullable=True),
    sa.Column("actor_id", postgresql.UUID(as_uuid=False), nullable=True),
    sa.Column("event_type", sa.String(), nullable=False),
    sa.Column("entity_type", sa.String(), nullable=False),
    sa.Column("entity_id", sa.String(), nullable=True),
    sa.Column("payload", postgresql.JSONB(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_audit_board_created", "audit_events", ["board_id", "created_at"], unique=False)
  op.create_index("ix_audit_task_created", "audit_events", ["task_id", "created_at"], unique=False)

  op.create_table(
    "jira_connections",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("base_url", sa.String(), nullable=False),
    sa.Column("email", sa.String(), nullable=True),
    sa.Column("token_encrypted", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  )

  op.create_table(
    "jira_sync_profiles",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("board_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("connection_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("jql", sa.Text(), nullable=False),
    sa.Column("status_to_state_key", postgresql.JSONB(), nullable=False),
    sa.Column("priority_map", postgresql.JSONB(), nullable=False),
    sa.Column("type_map", postgresql.JSONB(), nullable=False),
    sa.Column("conflict_policy", sa.String(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_jira_profiles_board", "jira_sync_profiles", ["board_id"], unique=False)

  op.create_table(
    "sync_runs",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("board_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("profile_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("status", sa.String(), nullable=False),
    sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("log", postgresql.JSONB(), nullable=False),
    sa.Column("error_message", sa.Text(), nullable=True),
  )
  op.create_index("ix_sync_runs_board_started", "sync_runs", ["board_id", "started_at"], unique=False)


def downgrade() -> None:
  op.drop_table("sync_runs")
  op.drop_table("jira_sync_profiles")
  op.drop_table("jira_connections")
  op.drop_table("audit_events")
  op.drop_table("attachments")
  op.drop_table("checklist_items")
  op.drop_table("comments")
  op.drop_table("task_dependencies")
  op.drop_table("tasks")
  op.drop_table("lanes")
  op.drop_table("board_members")
  op.drop_table("boards")
  op.drop_table("sessions")
  op.drop_table("users")

