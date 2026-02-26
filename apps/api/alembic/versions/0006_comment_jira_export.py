"""comment jira export

Revision ID: 0006_comment_jira_exp
Revises: 0005_jira_conn_assignee
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_comment_jira_exp"
down_revision = "0005_jira_conn_assignee"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("comments", sa.Column("jira_comment_id", sa.String(), nullable=True))
  op.add_column("comments", sa.Column("jira_exported_at", sa.DateTime(timezone=True), nullable=True))
  op.create_index("ix_comments_jira_comment_id", "comments", ["jira_comment_id"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_comments_jira_comment_id", table_name="comments")
  op.drop_column("comments", "jira_exported_at")
  op.drop_column("comments", "jira_comment_id")
