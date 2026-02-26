"""webhooks inbox + secrets

Revision ID: 0008_webhooks
Revises: 0007_user_board_admin
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_webhooks"
down_revision = "0007_user_board_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "webhook_secrets",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
    sa.Column("source", sa.String(), nullable=False),
    sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("bearer_token_encrypted", sa.Text(), nullable=False),
    sa.Column("token_hint", sa.String(), nullable=False, server_default=sa.text("''")),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
  )
  op.create_index("ix_webhook_secrets_source", "webhook_secrets", ["source"], unique=True)

  op.create_table(
    "inbound_webhook_events",
    sa.Column("id", sa.UUID(as_uuid=False), primary_key=True),
    sa.Column("source", sa.String(), nullable=False),
    sa.Column("idempotency_key", sa.String(), nullable=True),
    sa.Column("headers", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("body", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("result", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("error", sa.Text(), nullable=True),
    sa.UniqueConstraint("source", "idempotency_key", name="ux_inbound_webhook_source_idempotency"),
  )
  op.create_index("ix_inbound_webhook_events_source", "inbound_webhook_events", ["source"], unique=False)
  op.create_index("ix_inbound_webhook_events_processed", "inbound_webhook_events", ["processed"], unique=False)

  op.alter_column("webhook_secrets", "enabled", server_default=None)
  op.alter_column("webhook_secrets", "token_hint", server_default=None)


def downgrade() -> None:
  op.drop_index("ix_inbound_webhook_events_processed", table_name="inbound_webhook_events")
  op.drop_index("ix_inbound_webhook_events_source", table_name="inbound_webhook_events")
  op.drop_table("inbound_webhook_events")
  op.drop_index("ix_webhook_secrets_source", table_name="webhook_secrets")
  op.drop_table("webhook_secrets")

