from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.models import Task, TaskReminder
from app.notifications.events import dispatch_to_materialized, materialize_enabled_destinations, notify_inapp
from app.notifications.service import NotificationMessage


async def dispatch_due_reminders_once(db: AsyncSession, *, now: datetime | None = None, limit: int = 50) -> int:
  """
  Dispatch due reminders.

  - Always emits an in-app notification to the recipient.
  - Optionally emits "external" notifications (pushover/email/etc) to all enabled destinations.
  - Idempotent: reminders are claimed with a status transition and dedupe keys.
  """
  now = now or datetime.now(timezone.utc)

  res = await db.execute(
    select(TaskReminder)
    .where(
      TaskReminder.canceled_at.is_(None),
      TaskReminder.sent_at.is_(None),
      TaskReminder.scheduled_at <= now,
      TaskReminder.status.in_(["pending", "error"]),
      TaskReminder.attempts < 5,
    )
    .order_by(TaskReminder.scheduled_at.asc())
    .limit(int(limit))
  )
  reminders = res.scalars().all()
  if not reminders:
    return 0

  sent = 0
  for r in reminders:
    # Claim the reminder for sending (idempotent across multiple workers).
    claim = await db.execute(
      update(TaskReminder)
      .where(TaskReminder.id == r.id, TaskReminder.sent_at.is_(None), TaskReminder.status.in_(["pending", "error"]))
      .values(status="sending", attempts=TaskReminder.attempts + 1, last_attempt_at=now, last_error=None)
    )
    if claim.rowcount == 0:
      continue

    # Load task title for the notification.
    tres = await db.execute(select(Task).where(Task.id == r.task_id))
    t = tres.scalar_one_or_none()
    title = (t.title if t else "Task reminder").strip() or "Task reminder"
    body = title
    if r.note:
      body = f"{title}\n{r.note}"

    try:
      await notify_inapp(
        db,
        user_id=r.recipient_user_id,
        level="info",
        title="Reminder",
        body=body,
        event_type="reminder.due",
        entity_type="Task",
        entity_id=r.task_id,
        dedupe_key=f"reminder.due:{r.id}",
      )

      external_messages: list[NotificationMessage] = []
      if "external" in (r.channels or []):
        external_messages.append(NotificationMessage(title=f"Task-Daddy reminder: {title}", message=body, priority=0))
      external_dests = await materialize_enabled_destinations(db) if external_messages else []

      # Mark sent before external dispatch (external is best-effort).
      await db.execute(update(TaskReminder).where(TaskReminder.id == r.id).values(status="sent", sent_at=now))
      await write_audit(
        db,
        event_type="reminder.sent",
        entity_type="TaskReminder",
        entity_id=r.id,
        board_id=(t.board_id if t else None),
        task_id=r.task_id,
        actor_id=None,
        payload={"channels": list(r.channels or []), "attempts": int(r.attempts or 0) + 1},
      )
      await db.commit()

      for msg in external_messages:
        if external_dests:
          asyncio.create_task(dispatch_to_materialized(external_dests, msg=msg))

      sent += 1
    except Exception as e:
      await db.execute(update(TaskReminder).where(TaskReminder.id == r.id).values(status="error", last_error=str(e)))
      await db.commit()

  return sent

