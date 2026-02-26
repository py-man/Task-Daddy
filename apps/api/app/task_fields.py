from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BoardTaskPriority, BoardTaskType


def _now() -> datetime:
  return datetime.now(timezone.utc)


def default_task_types() -> list[dict]:
  return [
    {"key": "Bug", "name": "Bug", "color": "#ef4444", "position": 0},
    {"key": "Feature", "name": "Feature", "color": "#22c55e", "position": 1},
    {"key": "Ops", "name": "Ops", "color": "#38bdf8", "position": 2},
    {"key": "Risk", "name": "Risk", "color": "#f59e0b", "position": 3},
    {"key": "Debt", "name": "Debt", "color": "#a855f7", "position": 4},
    {"key": "Spike", "name": "Spike", "color": "#eab308", "position": 5},
    {"key": "Support", "name": "Support", "color": "#94a3b8", "position": 6},
  ]


def default_task_priorities() -> list[dict]:
  return [
    {"key": "P0", "name": "P0", "color": "#fb7185", "rank": 0},
    {"key": "P1", "name": "P1", "color": "#f59e0b", "rank": 1},
    {"key": "P2", "name": "P2", "color": "#60a5fa", "rank": 2},
    {"key": "P3", "name": "P3", "color": "#94a3b8", "rank": 3},
  ]


async def ensure_board_task_fields(db: AsyncSession, *, board_id: str) -> None:
  """
  Ensure a board has default task types + priorities.

  This is idempotent and safe to call on every boot/seed for existing boards.
  """
  types = default_task_types()
  prios = default_task_priorities()

  res_t = await db.execute(select(BoardTaskType).where(BoardTaskType.board_id == board_id))
  existing_types = {t.key: t for t in res_t.scalars().all()}
  for item in types:
    if item["key"] in existing_types:
      continue
    db.add(
      BoardTaskType(
        id=str(uuid.uuid4()),
        board_id=board_id,
        key=item["key"],
        name=item["name"],
        color=item.get("color"),
        enabled=True,
        position=int(item.get("position") or 0),
        created_at=_now(),
      )
    )

  res_p = await db.execute(select(BoardTaskPriority).where(BoardTaskPriority.board_id == board_id))
  existing_prios = {p.key: p for p in res_p.scalars().all()}
  for item in prios:
    if item["key"] in existing_prios:
      continue
    db.add(
      BoardTaskPriority(
        id=str(uuid.uuid4()),
        board_id=board_id,
        key=item["key"],
        name=item["name"],
        color=item.get("color"),
        enabled=True,
        rank=int(item.get("rank") or 0),
        created_at=_now(),
      )
    )

