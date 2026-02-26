"""in-app notifications

Revision ID: 0014_inapp_notifs
Revises: 0013_fix_notif_id
Create Date: 2026-02-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0014_inapp_notifs"
down_revision = "0013_fix_notif_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "in_app_notifications",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, nullable=False),
    sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("level", sa.String(), nullable=False, server_default=sa.text("'info'")),
    sa.Column("title", sa.String(), nullable=False),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("event_type", sa.String(), nullable=True),
    sa.Column("entity_type", sa.String(), nullable=True),
    sa.Column("entity_id", sa.String(), nullable=True),
    sa.Column("dedupe_key", sa.String(), nullable=True),
    sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
  )
  op.create_index("ix_in_app_notifications_user_id", "in_app_notifications", ["user_id"])
  op.create_index(
    "ux_inapp_notifications_user_dedupe_key",
    "in_app_notifications",
    ["user_id", "dedupe_key"],
    unique=True,
    postgresql_where=sa.text("dedupe_key IS NOT NULL"),
  )


def downgrade() -> None:
  op.drop_index("ux_inapp_notifications_user_dedupe_key", table_name="in_app_notifications")
  op.drop_index("ix_in_app_notifications_user_id", table_name="in_app_notifications")
  op.drop_table("in_app_notifications")

