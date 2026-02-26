"""notification prefs + quiet hours

Revision ID: 0019_notif_prefs
Revises: 0018_api_tokens
Create Date: 2026-02-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0019_notif_prefs"
down_revision = "0018_api_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("users", sa.Column("notification_prefs", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")))
  op.add_column("users", sa.Column("quiet_hours_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
  op.add_column("users", sa.Column("quiet_hours_start", sa.String(), nullable=True))
  op.add_column("users", sa.Column("quiet_hours_end", sa.String(), nullable=True))


def downgrade() -> None:
  op.drop_column("users", "quiet_hours_end")
  op.drop_column("users", "quiet_hours_start")
  op.drop_column("users", "quiet_hours_enabled")
  op.drop_column("users", "notification_prefs")
