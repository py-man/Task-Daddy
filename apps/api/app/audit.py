from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def write_audit(
  db: AsyncSession,
  *,
  event_type: str,
  entity_type: str,
  entity_id: str | None,
  board_id: str | None = None,
  task_id: str | None = None,
  actor_id: str | None = None,
  payload: dict[str, Any] | None = None,
) -> None:
  safe_payload = jsonable_encoder(payload or {})
  ev = AuditEvent(
    board_id=board_id,
    task_id=task_id,
    actor_id=actor_id,
    event_type=event_type,
    entity_type=entity_type,
    entity_id=entity_id,
    payload=safe_payload,
  )
  db.add(ev)
