"""task reminders

Revision ID: 0016_task_reminders
Revises: 0015_task_import_keys
Create Date: 2026-02-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0016_task_reminders"
down_revision = "0015_task_import_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "task_reminders",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, nullable=False),
    sa.Column("task_id", sa.UUID(as_uuid=False), sa.ForeignKey("tasks.id"), nullable=False),
    sa.Column("board_id", sa.UUID(as_uuid=False), sa.ForeignKey("boards.id"), nullable=False),
    sa.Column("created_by_user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("recipient_user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("note", sa.Text(), nullable=False, server_default=""),
    sa.Column("channels", sa.JSON(), nullable=False, server_default=sa.text("'[\"inapp\"]'::json")),
    sa.Column("status", sa.String(), nullable=False, server_default="pending"),  # pending|sending|sent|error|canceled
    sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("last_error", sa.Text(), nullable=True),
    sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
  )
  op.create_index("ix_task_reminders_task_id", "task_reminders", ["task_id"])
  op.create_index("ix_task_reminders_board_id", "task_reminders", ["board_id"])
  op.create_index("ix_task_reminders_recipient_user_id", "task_reminders", ["recipient_user_id"])
  op.create_index("ix_task_reminders_scheduled_at", "task_reminders", ["scheduled_at"])
  op.create_index("ix_task_reminders_status", "task_reminders", ["status"])


def downgrade() -> None:
  op.drop_index("ix_task_reminders_status", table_name="task_reminders")
  op.drop_index("ix_task_reminders_scheduled_at", table_name="task_reminders")
  op.drop_index("ix_task_reminders_recipient_user_id", table_name="task_reminders")
  op.drop_index("ix_task_reminders_board_id", table_name="task_reminders")
  op.drop_index("ix_task_reminders_task_id", table_name="task_reminders")
  op.drop_table("task_reminders")

