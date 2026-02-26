"""board member unique constraint

Revision ID: 0011_board_member_unique
Revises: 0010_board_name_key_unique
Create Date: 2026-02-23
"""

from __future__ import annotations

from alembic import op


revision = "0011_board_member_unique"
down_revision = "0010_board_name_key_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_unique_constraint("ux_board_member_board_user", "board_members", ["board_id", "user_id"])


def downgrade() -> None:
  op.drop_constraint("ux_board_member_board_user", "board_members", type_="unique")

