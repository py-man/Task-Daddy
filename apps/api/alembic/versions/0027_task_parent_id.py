"""add task parent id

Revision ID: 0027_task_parent_id
Revises: 0026_github_connections
Create Date: 2026-03-04 16:35:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0027_task_parent_id"
down_revision = "0026_github_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
    "tasks",
    sa.Column("parent_task_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
  )
  op.create_index("ix_tasks_parent_task_id", "tasks", ["parent_task_id"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_tasks_parent_task_id", table_name="tasks")
  op.drop_column("tasks", "parent_task_id")
