"""notification taxonomy and burst collapse fields

Revision ID: 0021_notif_taxonomy_burst
Revises: 0020_backup_policy
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0021_notif_taxonomy_burst"
down_revision = "0020_backup_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("in_app_notifications", sa.Column("taxonomy", sa.String(), nullable=False, server_default=sa.text("'informational'")))
  op.add_column("in_app_notifications", sa.Column("burst_count", sa.Integer(), nullable=False, server_default=sa.text("1")))
  op.add_column("in_app_notifications", sa.Column("last_occurrence_at", sa.DateTime(timezone=True), nullable=True))
  op.execute("UPDATE in_app_notifications SET last_occurrence_at = created_at WHERE last_occurrence_at IS NULL")


def downgrade() -> None:
  op.drop_column("in_app_notifications", "last_occurrence_at")
  op.drop_column("in_app_notifications", "burst_count")
  op.drop_column("in_app_notifications", "taxonomy")
