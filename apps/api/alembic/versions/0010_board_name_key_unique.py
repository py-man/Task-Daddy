"""board name unique key

Revision ID: 0010_board_name_key_unique
Revises: 0009_security_mfa_reset_sessions
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_board_name_key_unique"
down_revision = "0009_security_mfa_reset_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("boards", sa.Column("name_key", sa.String(), nullable=True))
  op.execute("UPDATE boards SET name_key = lower(trim(name)) WHERE name_key IS NULL")
  op.alter_column("boards", "name_key", nullable=False)
  op.create_unique_constraint("ux_boards_name_key", "boards", ["name_key"])
  op.create_index("ix_boards_name_key", "boards", ["name_key"])


def downgrade() -> None:
  op.drop_index("ix_boards_name_key", table_name="boards")
  op.drop_constraint("ux_boards_name_key", "boards", type_="unique")
  op.drop_column("boards", "name_key")

