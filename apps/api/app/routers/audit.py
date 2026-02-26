from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db, require_board_role
from app.models import AuditEvent, Task, User
from app.schemas import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
async def list_audit(
  boardId: str | None = None,
  taskId: str | None = None,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> list[AuditOut]:
  if boardId:
    await require_board_role(boardId, "viewer", user, db)
  elif taskId:
    tres = await db.execute(select(Task).where(Task.id == taskId))
    t = tres.scalar_one_or_none()
    if t:
      await require_board_role(t.board_id, "viewer", user, db)
  q = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(200)
  if boardId:
    q = q.where(AuditEvent.board_id == boardId)
  if taskId:
    q = q.where(AuditEvent.task_id == taskId)
  res = await db.execute(q)
  out = []
  for ev in res.scalars().all():
    out.append(
      AuditOut(
        id=ev.id,
        boardId=ev.board_id,
        taskId=ev.task_id,
        actorId=ev.actor_id,
        eventType=ev.event_type,
        entityType=ev.entity_type,
        entityId=ev.entity_id,
        payload=ev.payload,
        createdAt=ev.created_at,
      )
    )
  return out
