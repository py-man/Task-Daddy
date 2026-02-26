from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import write_audit
from app.deps import get_current_user, get_db, require_board_role
from app.models import BoardTaskPriority, BoardTaskType, Task, User
from app.schemas import (
  BoardTaskPriorityCreateIn,
  BoardTaskPriorityOut,
  BoardTaskPriorityReorderIn,
  BoardTaskPriorityUpdateIn,
  BoardTaskTypeCreateIn,
  BoardTaskTypeOut,
  BoardTaskTypeReorderIn,
  BoardTaskTypeUpdateIn,
)
from app.task_fields import ensure_board_task_fields

router = APIRouter(tags=["taskFields"])


def _norm_key(s: str) -> str:
  return (s or "").strip()


@router.get("/boards/{board_id}/task_types", response_model=list[BoardTaskTypeOut])
async def list_task_types(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[BoardTaskTypeOut]:
  await require_board_role(board_id, "viewer", user, db)
  await ensure_board_task_fields(db, board_id=board_id)
  res = await db.execute(select(BoardTaskType).where(BoardTaskType.board_id == board_id).order_by(BoardTaskType.position.asc()))
  return [BoardTaskTypeOut(key=t.key, name=t.name, color=t.color, enabled=bool(t.enabled), position=int(t.position or 0)) for t in res.scalars().all()]


@router.post("/boards/{board_id}/task_types", response_model=BoardTaskTypeOut)
async def create_task_type(
  board_id: str, payload: BoardTaskTypeCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> BoardTaskTypeOut:
  await require_board_role(board_id, "admin", user, db)
  key = _norm_key(payload.key)
  name = (payload.name or "").strip()
  if not key or not name:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key/name")

  max_pos = (await db.execute(select(func.max(BoardTaskType.position)).where(BoardTaskType.board_id == board_id))).scalar_one()
  pos = int(max_pos + 1) if max_pos is not None else 0
  t = BoardTaskType(id=str(uuid.uuid4()), board_id=board_id, key=key, name=name, color=payload.color, enabled=True, position=pos)
  db.add(t)
  try:
    await db.flush()
  except IntegrityError as e:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Type key already exists") from e
  await write_audit(
    db,
    event_type="board.task_type.created",
    entity_type="BoardTaskType",
    entity_id=t.id,
    board_id=board_id,
    actor_id=user.id,
    payload={"key": key, "name": name},
  )
  await db.commit()
  return BoardTaskTypeOut(key=t.key, name=t.name, color=t.color, enabled=bool(t.enabled), position=int(t.position or 0))


@router.patch("/boards/{board_id}/task_types/{key}", response_model=BoardTaskTypeOut)
async def update_task_type(
  board_id: str,
  key: str,
  payload: BoardTaskTypeUpdateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> BoardTaskTypeOut:
  await require_board_role(board_id, "admin", user, db)
  k = _norm_key(key)
  res = await db.execute(select(BoardTaskType).where(BoardTaskType.board_id == board_id, BoardTaskType.key == k))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Type not found")
  if payload.name is not None:
    t.name = payload.name.strip()
  if payload.color is not None:
    t.color = payload.color
  if payload.enabled is not None:
    t.enabled = bool(payload.enabled)
  await write_audit(
    db,
    event_type="board.task_type.updated",
    entity_type="BoardTaskType",
    entity_id=t.id,
    board_id=board_id,
    actor_id=user.id,
    payload={"key": t.key},
  )
  await db.commit()
  return BoardTaskTypeOut(key=t.key, name=t.name, color=t.color, enabled=bool(t.enabled), position=int(t.position or 0))


@router.post("/boards/{board_id}/task_types/reorder")
async def reorder_task_types(
  board_id: str, payload: BoardTaskTypeReorderIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
  await require_board_role(board_id, "admin", user, db)
  keys = [_norm_key(k) for k in payload.keys if _norm_key(k)]
  res = await db.execute(select(BoardTaskType.key).where(BoardTaskType.board_id == board_id))
  existing = set([k for k in res.scalars().all() if k])
  if set(keys) != existing:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="keys must include all existing type keys exactly once")
  for idx, k in enumerate(keys):
    await db.execute(update(BoardTaskType).where(BoardTaskType.board_id == board_id, BoardTaskType.key == k).values(position=idx))
  await write_audit(
    db,
    event_type="board.task_type.reordered",
    entity_type="Board",
    entity_id=board_id,
    board_id=board_id,
    actor_id=user.id,
    payload={"keys": keys},
  )
  await db.commit()
  return {"ok": True}


@router.delete("/boards/{board_id}/task_types/{key}")
async def delete_task_type(board_id: str, key: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await require_board_role(board_id, "admin", user, db)
  k = _norm_key(key)
  # prevent deleting if in use
  used = (await db.execute(select(func.count()).select_from(Task).where(Task.board_id == board_id, Task.type == k))).scalar_one()
  if used and int(used) > 0:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Type is in use; disable it instead")
  res = await db.execute(select(BoardTaskType).where(BoardTaskType.board_id == board_id, BoardTaskType.key == k))
  t = res.scalar_one_or_none()
  if not t:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Type not found")
  await db.delete(t)
  await write_audit(
    db,
    event_type="board.task_type.deleted",
    entity_type="BoardTaskType",
    entity_id=t.id,
    board_id=board_id,
    actor_id=user.id,
    payload={"key": k},
  )
  await db.commit()
  return {"ok": True}


@router.get("/boards/{board_id}/priorities", response_model=list[BoardTaskPriorityOut])
async def list_priorities(board_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> list[BoardTaskPriorityOut]:
  await require_board_role(board_id, "viewer", user, db)
  await ensure_board_task_fields(db, board_id=board_id)
  res = await db.execute(select(BoardTaskPriority).where(BoardTaskPriority.board_id == board_id).order_by(BoardTaskPriority.rank.asc()))
  return [BoardTaskPriorityOut(key=p.key, name=p.name, color=p.color, enabled=bool(p.enabled), rank=int(p.rank or 0)) for p in res.scalars().all()]


@router.post("/boards/{board_id}/priorities", response_model=BoardTaskPriorityOut)
async def create_priority(
  board_id: str, payload: BoardTaskPriorityCreateIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> BoardTaskPriorityOut:
  await require_board_role(board_id, "admin", user, db)
  key = _norm_key(payload.key)
  name = (payload.name or "").strip()
  if not key or not name:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid key/name")

  max_rank = (await db.execute(select(func.max(BoardTaskPriority.rank)).where(BoardTaskPriority.board_id == board_id))).scalar_one()
  rank = int(payload.rank) if payload.rank is not None else (int(max_rank + 1) if max_rank is not None else 0)
  p = BoardTaskPriority(id=str(uuid.uuid4()), board_id=board_id, key=key, name=name, color=payload.color, enabled=True, rank=rank)
  db.add(p)
  try:
    await db.flush()
  except IntegrityError as e:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Priority key already exists") from e
  await write_audit(
    db,
    event_type="board.priority.created",
    entity_type="BoardTaskPriority",
    entity_id=p.id,
    board_id=board_id,
    actor_id=user.id,
    payload={"key": key, "name": name},
  )
  await db.commit()
  return BoardTaskPriorityOut(key=p.key, name=p.name, color=p.color, enabled=bool(p.enabled), rank=int(p.rank or 0))


@router.patch("/boards/{board_id}/priorities/{key}", response_model=BoardTaskPriorityOut)
async def update_priority(
  board_id: str,
  key: str,
  payload: BoardTaskPriorityUpdateIn,
  user: User = Depends(get_current_user),
  db: AsyncSession = Depends(get_db),
) -> BoardTaskPriorityOut:
  await require_board_role(board_id, "admin", user, db)
  k = _norm_key(key)
  res = await db.execute(select(BoardTaskPriority).where(BoardTaskPriority.board_id == board_id, BoardTaskPriority.key == k))
  p = res.scalar_one_or_none()
  if not p:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Priority not found")
  if payload.name is not None:
    p.name = payload.name.strip()
  if payload.color is not None:
    p.color = payload.color
  if payload.enabled is not None:
    p.enabled = bool(payload.enabled)
  await write_audit(
    db,
    event_type="board.priority.updated",
    entity_type="BoardTaskPriority",
    entity_id=p.id,
    board_id=board_id,
    actor_id=user.id,
    payload={"key": p.key},
  )
  await db.commit()
  return BoardTaskPriorityOut(key=p.key, name=p.name, color=p.color, enabled=bool(p.enabled), rank=int(p.rank or 0))


@router.post("/boards/{board_id}/priorities/reorder")
async def reorder_priorities(
  board_id: str, payload: BoardTaskPriorityReorderIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
  await require_board_role(board_id, "admin", user, db)
  keys = [_norm_key(k) for k in payload.keys if _norm_key(k)]
  res = await db.execute(select(BoardTaskPriority.key).where(BoardTaskPriority.board_id == board_id))
  existing = set([k for k in res.scalars().all() if k])
  if set(keys) != existing:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="keys must include all existing priority keys exactly once")
  for idx, k in enumerate(keys):
    await db.execute(update(BoardTaskPriority).where(BoardTaskPriority.board_id == board_id, BoardTaskPriority.key == k).values(rank=idx))
  await write_audit(
    db,
    event_type="board.priority.reordered",
    entity_type="Board",
    entity_id=board_id,
    board_id=board_id,
    actor_id=user.id,
    payload={"keys": keys},
  )
  await db.commit()
  return {"ok": True}


@router.delete("/boards/{board_id}/priorities/{key}")
async def delete_priority(board_id: str, key: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
  await require_board_role(board_id, "admin", user, db)
  k = _norm_key(key)
  used = (await db.execute(select(func.count()).select_from(Task).where(Task.board_id == board_id, Task.priority == k))).scalar_one()
  if used and int(used) > 0:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Priority is in use; disable it instead")
  res = await db.execute(select(BoardTaskPriority).where(BoardTaskPriority.board_id == board_id, BoardTaskPriority.key == k))
  p = res.scalar_one_or_none()
  if not p:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Priority not found")
  await db.delete(p)
  await write_audit(
    db,
    event_type="board.priority.deleted",
    entity_type="BoardTaskPriority",
    entity_id=p.id,
    board_id=board_id,
    actor_id=user.id,
    payload={"key": k},
  )
  await db.commit()
  return {"ok": True}

