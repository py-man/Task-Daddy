"""backup policy guardrails

Revision ID: 0020_backup_policy
Revises: 0019_notif_prefs
Create Date: 2026-02-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0020_backup_policy"
down_revision = "0019_notif_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "backup_policies",
    sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("retention_days", sa.Integer(), nullable=False, server_default="5"),
    sa.Column("min_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
    sa.Column("max_backups", sa.Integer(), nullable=False, server_default="30"),
    sa.Column("max_total_size_mb", sa.Integer(), nullable=False, server_default="2048"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.PrimaryKeyConstraint("id"),
  )


def downgrade() -> None:
  op.drop_table("backup_policies")
