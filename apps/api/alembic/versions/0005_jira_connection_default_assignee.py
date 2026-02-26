"""jira connection default assignee

Revision ID: 0005_jira_conn_assignee
Revises: 0004_comment_sources
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_jira_conn_assignee"
down_revision = "0004_comment_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("jira_connections", sa.Column("default_assignee_account_id", sa.String(), nullable=True))


def downgrade() -> None:
  op.drop_column("jira_connections", "default_assignee_account_id")
