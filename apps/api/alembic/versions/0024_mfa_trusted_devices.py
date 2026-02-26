"""mfa trusted devices

Revision ID: 0024_mfa_trusted_devices
Revises: 0023_openproject_task_linkage
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0024_mfa_trusted_devices"
down_revision = "0023_openproject_task_linkage"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "mfa_trusted_devices",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("token_hash", sa.String(), nullable=False),
    sa.Column("created_ip", sa.String(), nullable=True),
    sa.Column("user_agent", sa.String(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.create_index("ix_mfa_trusted_devices_user_id", "mfa_trusted_devices", ["user_id"], unique=False)
  op.create_index("ix_mfa_trusted_devices_token_hash", "mfa_trusted_devices", ["token_hash"], unique=True)


def downgrade() -> None:
  op.drop_index("ix_mfa_trusted_devices_token_hash", table_name="mfa_trusted_devices")
  op.drop_index("ix_mfa_trusted_devices_user_id", table_name="mfa_trusted_devices")
  op.drop_table("mfa_trusted_devices")
