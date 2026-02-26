"""openproject connections

Revision ID: 0022_openproject_connections
Revises: 0021_notif_taxonomy_burst
Create Date: 2026-02-25 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0022_openproject_connections"
down_revision = "0021_notif_taxonomy_burst"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "openproject_connections",
    sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("name", sa.String(), nullable=False, server_default=sa.text("'OpenProject'")),
    sa.Column("base_url", sa.String(), nullable=False),
    sa.Column("api_token_encrypted", sa.Text(), nullable=False),
    sa.Column("project_identifier", sa.String(), nullable=True),
    sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    sa.Column("token_hint", sa.String(), nullable=False, server_default=sa.text("''")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index("ix_openproject_connections_base_url", "openproject_connections", ["base_url"])


def downgrade() -> None:
  op.drop_index("ix_openproject_connections_base_url", table_name="openproject_connections")
  op.drop_table("openproject_connections")
