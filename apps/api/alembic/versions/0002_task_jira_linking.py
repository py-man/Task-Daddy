"""task jira linking

Revision ID: 0002_task_jira_linking
Revises: 0001_init
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_task_jira_linking"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("tasks", sa.Column("jira_connection_id", postgresql.UUID(as_uuid=False), nullable=True))
  op.add_column("tasks", sa.Column("jira_sync_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
  op.add_column("tasks", sa.Column("jira_project_key", sa.String(), nullable=True))
  op.add_column("tasks", sa.Column("jira_issue_type", sa.String(), nullable=True))

  op.create_index("ix_tasks_jira_connection", "tasks", ["jira_connection_id"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_tasks_jira_connection", table_name="tasks")
  op.drop_column("tasks", "jira_issue_type")
  op.drop_column("tasks", "jira_project_key")
  op.drop_column("tasks", "jira_sync_enabled")
  op.drop_column("tasks", "jira_connection_id")

