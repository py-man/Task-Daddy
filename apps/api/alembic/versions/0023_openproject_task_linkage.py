"""openproject task linkage fields

Revision ID: 0023_openproject_task_linkage
Revises: 0022_openproject_connections
Create Date: 2026-02-25 23:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0023_openproject_task_linkage"
down_revision = "0022_openproject_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("tasks", sa.Column("openproject_work_package_id", sa.Integer(), nullable=True))
  op.add_column("tasks", sa.Column("openproject_url", sa.String(), nullable=True))
  op.add_column("tasks", sa.Column("openproject_connection_id", postgresql.UUID(as_uuid=False), nullable=True))
  op.add_column("tasks", sa.Column("openproject_sync_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
  op.add_column("tasks", sa.Column("openproject_updated_at", sa.DateTime(timezone=True), nullable=True))
  op.add_column("tasks", sa.Column("openproject_last_sync_at", sa.DateTime(timezone=True), nullable=True))
  op.create_foreign_key(
    "fk_tasks_openproject_connection_id_openproject_connections",
    "tasks",
    "openproject_connections",
    ["openproject_connection_id"],
    ["id"],
  )
  op.create_index("ix_tasks_openproject_work_package_id", "tasks", ["openproject_work_package_id"])


def downgrade() -> None:
  op.drop_index("ix_tasks_openproject_work_package_id", table_name="tasks")
  op.drop_constraint("fk_tasks_openproject_connection_id_openproject_connections", "tasks", type_="foreignkey")
  op.drop_column("tasks", "openproject_last_sync_at")
  op.drop_column("tasks", "openproject_updated_at")
  op.drop_column("tasks", "openproject_sync_enabled")
  op.drop_column("tasks", "openproject_connection_id")
  op.drop_column("tasks", "openproject_url")
  op.drop_column("tasks", "openproject_work_package_id")
