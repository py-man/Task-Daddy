"""user fields + board name uniqueness

Revision ID: 0007_user_board_admin
Revises: 0006_comment_jira_exp
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_user_board_admin"
down_revision = "0006_comment_jira_exp"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("users", sa.Column("timezone", sa.String(), nullable=True))
  op.add_column("users", sa.Column("jira_account_id", sa.String(), nullable=True))
  op.add_column("users", sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
  op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")))
  op.create_index("ix_users_active", "users", ["active"], unique=False)
  op.create_index("ix_users_jira_account_id", "users", ["jira_account_id"], unique=False)
  op.alter_column("users", "active", server_default=None)

  # prevent duplicate board names globally (case-insensitive, trimmed)
  #
  # Older DBs may already contain duplicates (e.g. repeated smoke runs). We must
  # resolve those rows before creating the unique expression index, otherwise
  # the migration crashes and the API never boots.
  conn = op.get_bind()
  conn.execute(sa.text("UPDATE boards SET name = btrim(name) WHERE name <> btrim(name)"))
  conn.execute(
    sa.text(
      """
      WITH ranked AS (
        SELECT
          id,
          name,
          row_number() OVER (
            PARTITION BY lower(btrim(name))
            ORDER BY created_at ASC, id ASC
          ) AS rn
        FROM boards
      )
      UPDATE boards b
      SET name = btrim(b.name) || ' (dedup-' || substring(replace(b.id::text,'-','') from 1 for 8) || ')'
      FROM ranked r
      WHERE b.id = r.id AND r.rn > 1
      """
    )
  )
  op.create_index(
    "ux_boards_name_norm",
    "boards",
    [sa.text("lower(btrim(name))")],
    unique=True,
  )


def downgrade() -> None:
  op.drop_index("ux_boards_name_norm", table_name="boards")
  op.drop_index("ix_users_jira_account_id", table_name="users")
  op.drop_index("ix_users_active", table_name="users")
  op.drop_column("users", "updated_at")
  op.drop_column("users", "active")
  op.drop_column("users", "jira_account_id")
  op.drop_column("users", "timezone")
