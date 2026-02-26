"""board task fields (types, priorities)

Revision ID: 0017_board_task_fields
Revises: 0016_task_reminders
Create Date: 2026-02-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0017_board_task_fields"
down_revision = "0016_task_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "board_task_types",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, nullable=False),
    sa.Column("board_id", sa.UUID(as_uuid=False), sa.ForeignKey("boards.id"), nullable=False),
    sa.Column("key", sa.String(length=64), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("color", sa.String(length=32), nullable=True),
    sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
    sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
  )
  op.create_index("ix_board_task_types_board_id", "board_task_types", ["board_id"])
  op.create_unique_constraint("ux_board_task_types_board_key", "board_task_types", ["board_id", "key"])

  op.create_table(
    "board_task_priorities",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, nullable=False),
    sa.Column("board_id", sa.UUID(as_uuid=False), sa.ForeignKey("boards.id"), nullable=False),
    sa.Column("key", sa.String(length=64), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("color", sa.String(length=32), nullable=True),
    sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
  )
  op.create_index("ix_board_task_priorities_board_id", "board_task_priorities", ["board_id"])
  op.create_unique_constraint("ux_board_task_priorities_board_key", "board_task_priorities", ["board_id", "key"])


def downgrade() -> None:
  op.drop_constraint("ux_board_task_priorities_board_key", "board_task_priorities", type_="unique")
  op.drop_index("ix_board_task_priorities_board_id", table_name="board_task_priorities")
  op.drop_table("board_task_priorities")

  op.drop_constraint("ux_board_task_types_board_key", "board_task_types", type_="unique")
  op.drop_index("ix_board_task_types_board_id", table_name="board_task_types")
  op.drop_table("board_task_types")

