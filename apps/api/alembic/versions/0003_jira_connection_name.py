"""jira connection name

Revision ID: 0003_jira_connection_name
Revises: 0002_task_jira_linking
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_jira_connection_name"
down_revision = "0002_task_jira_linking"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("jira_connections", sa.Column("name", sa.String(), nullable=True))
  op.create_index("ix_jira_connections_name", "jira_connections", ["name"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_jira_connections_name", table_name="jira_connections")
  op.drop_column("jira_connections", "name")

