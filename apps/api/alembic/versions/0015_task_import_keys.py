"""task import keys

Revision ID: 0015_task_import_keys
Revises: 0014_inapp_notifs
Create Date: 2026-02-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0015_task_import_keys"
down_revision = "0014_inapp_notifs"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "task_import_keys",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, nullable=False),
    sa.Column("board_id", sa.UUID(as_uuid=False), sa.ForeignKey("boards.id"), nullable=False),
    sa.Column("key", sa.Text(), nullable=False),
    sa.Column("task_id", sa.UUID(as_uuid=False), sa.ForeignKey("tasks.id"), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
  )
  op.create_index("ix_task_import_keys_board_id", "task_import_keys", ["board_id"])
  op.create_unique_constraint("ux_task_import_board_key", "task_import_keys", ["board_id", "key"])


def downgrade() -> None:
  op.drop_constraint("ux_task_import_board_key", "task_import_keys", type_="unique")
  op.drop_index("ix_task_import_keys_board_id", table_name="task_import_keys")
  op.drop_table("task_import_keys")

