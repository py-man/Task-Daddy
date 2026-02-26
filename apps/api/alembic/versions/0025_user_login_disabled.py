"""add user login_disabled flag

Revision ID: 0025_user_login_disabled
Revises: 0024_mfa_trusted_devices
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0025_user_login_disabled"
down_revision = "0024_mfa_trusted_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("users", sa.Column("login_disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
  op.alter_column("users", "login_disabled", server_default=None)


def downgrade() -> None:
  op.drop_column("users", "login_disabled")

