"""comment sources

Revision ID: 0004_comment_sources
Revises: 0003_jira_connection_name
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_comment_sources"
down_revision = "0003_jira_connection_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("comments", sa.Column("source", sa.String(), nullable=False, server_default="app"))
  op.add_column("comments", sa.Column("source_id", sa.String(), nullable=True))
  op.add_column("comments", sa.Column("source_author", sa.String(), nullable=True))
  op.add_column("comments", sa.Column("source_url", sa.String(), nullable=True))
  op.create_index(
    "ux_comments_task_source_source_id",
    "comments",
    ["task_id", "source", "source_id"],
    unique=True,
  )
  op.alter_column("comments", "source", server_default=None)


def downgrade() -> None:
  op.drop_index("ux_comments_task_source_source_id", table_name="comments")
  op.drop_column("comments", "source_url")
  op.drop_column("comments", "source_author")
  op.drop_column("comments", "source_id")
  op.drop_column("comments", "source")

