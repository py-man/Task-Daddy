"""security mfa + password reset + session metadata

Revision ID: 0009_security_mfa_reset_sessions
Revises: 0008_webhooks
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_security_mfa_reset_sessions"
down_revision = "0008_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
  op.add_column("users", sa.Column("mfa_secret_encrypted", sa.Text(), nullable=True))
  op.add_column("users", sa.Column("mfa_recovery_codes_encrypted", sa.Text(), nullable=True))

  op.add_column("sessions", sa.Column("mfa_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))
  op.add_column("sessions", sa.Column("created_ip", sa.String(), nullable=True))
  op.add_column("sessions", sa.Column("user_agent", sa.String(), nullable=True))

  op.create_table(
    "password_reset_tokens",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False, index=True),
    sa.Column("token_hash", sa.String(), nullable=False, unique=True, index=True),
    sa.Column("request_ip", sa.String(), nullable=True),
    sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
  )


def downgrade() -> None:
  op.drop_table("password_reset_tokens")
  op.drop_column("sessions", "user_agent")
  op.drop_column("sessions", "created_ip")
  op.drop_column("sessions", "mfa_verified")
  op.drop_column("users", "mfa_recovery_codes_encrypted")
  op.drop_column("users", "mfa_secret_encrypted")
  op.drop_column("users", "mfa_enabled")
