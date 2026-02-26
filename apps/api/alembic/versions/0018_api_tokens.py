"""api tokens (personal access tokens)

Revision ID: 0018_api_tokens
Revises: 0017_board_task_fields
Create Date: 2026-02-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0018_api_tokens"
down_revision = "0017_board_task_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "api_tokens",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True, nullable=False),
    sa.Column("user_id", sa.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
    sa.Column("name", sa.String(length=200), nullable=False),
    sa.Column("token_hash", sa.String(length=128), nullable=False),
    sa.Column("token_hint", sa.String(length=32), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
  )
  op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])
  op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
  op.drop_index("ix_api_tokens_token_hash", table_name="api_tokens")
  op.drop_index("ix_api_tokens_user_id", table_name="api_tokens")
  op.drop_table("api_tokens")

