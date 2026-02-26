"""fix notification_destinations.id to UUID

Revision ID: 0013_fix_notif_id
Revises: 0012_notifications
Create Date: 2026-02-23
"""

from alembic import op


revision = "0013_fix_notif_id"
down_revision = "0012_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
  # 0012 created id as varchar by mistake; fix to UUID without breaking already-correct installs.
  op.execute(
    """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'notification_destinations'
      AND column_name = 'id'
      AND data_type IN ('character varying', 'text')
  ) THEN
    ALTER TABLE notification_destinations
      ALTER COLUMN id TYPE uuid USING id::uuid;
  END IF;
END $$;
"""
  )


def downgrade() -> None:
  op.execute(
    """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'notification_destinations'
      AND column_name = 'id'
      AND data_type = 'uuid'
  ) THEN
    ALTER TABLE notification_destinations
      ALTER COLUMN id TYPE varchar USING id::text;
  END IF;
END $$;
"""
  )

