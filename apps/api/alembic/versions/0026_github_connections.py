"""github connections

Revision ID: 0026_github_connections
Revises: 0025_user_login_disabled
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0026_github_connections"
down_revision = "0025_user_login_disabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "github_connections",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, nullable=False),
    sa.Column("name", sa.String(), nullable=False, server_default="GitHub"),
    sa.Column("base_url", sa.String(), nullable=False, server_default="https://api.github.com"),
    sa.Column("api_token_encrypted", sa.Text(), nullable=False),
    sa.Column("default_owner", sa.String(), nullable=True),
    sa.Column("default_repo", sa.String(), nullable=True),
    sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("token_hint", sa.String(), nullable=False, server_default=""),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
  )


def downgrade() -> None:
  op.drop_table("github_connections")

