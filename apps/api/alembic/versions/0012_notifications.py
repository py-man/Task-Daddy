"""notifications destinations

Revision ID: 0012_notifications
Revises: 0011_board_member_unique
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_notifications"
down_revision = "0011_board_member_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "notification_destinations",
    sa.Column("id", sa.String(), primary_key=True, nullable=False),
    sa.Column("provider", sa.String(), nullable=False),
    sa.Column("name", sa.String(), nullable=False, server_default="Default"),
    sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("config_encrypted", sa.Text(), nullable=False),
    sa.Column("token_hint", sa.String(), nullable=False, server_default=""),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
  )
  op.create_index("ix_notification_destinations_provider", "notification_destinations", ["provider"])


def downgrade() -> None:
  op.drop_index("ix_notification_destinations_provider", table_name="notification_destinations")
  op.drop_table("notification_destinations")

